"""Transport preflight must separate a broken task environment from source failures."""

from pathlib import Path
import io
import socket
import sys
import unittest
import urllib.error
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import network_preflight
import orchestrate_daily


class _Response:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class NetworkPreflightTests(unittest.TestCase):
    def test_dead_local_proxy_fails_before_any_source_request(self):
        calls = []

        def refused(*_args, **_kwargs):
            raise ConnectionRefusedError(10061, "connection refused")

        def opener(*_args, **_kwargs):
            calls.append("source request")
            return _Response(200)

        result = network_preflight.inspect_network(
            proxies={"https": "http://127.0.0.1:9"}, connector=refused, opener=opener)
        self.assertEqual(result["status"], "environment_blocked")
        self.assertEqual(result["reason"], "local_https_proxy_refused")
        self.assertEqual(calls, [])

    def test_timed_out_local_proxy_is_also_an_environment_block(self):
        def timed_out(*_args, **_kwargs):
            raise socket.timeout("timed out")

        result = network_preflight.inspect_network(
            proxies={"https": "http://127.0.0.1:9"}, connector=timed_out)
        self.assertEqual(result["status"], "environment_blocked")
        self.assertEqual(result["reason"], "local_https_proxy_unreachable")
        self.assertEqual(result["probes"], [])

    def test_single_source_http_error_does_not_disable_collection(self):
        def opener(request, **_kwargs):
            if "feeds.aps.org" in request.full_url:
                raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO())
            return _Response(200)

        result = network_preflight.inspect_network(proxies={}, opener=opener)
        self.assertEqual(result["status"], "ready")
        self.assertEqual([probe["http_status"] for probe in result["probes"]], [403, 200])
        self.assertEqual(result["policy_enforcement"], "not_verified")

    def test_http_429_is_source_result_not_environment_block(self):
        result = network_preflight.inspect_network(
            proxies={}, opener=lambda *_args, **_kwargs: _Response(429))
        self.assertEqual(result["status"], "ready")

    def test_both_sources_refuse_connection(self):
        def refused(request, **_kwargs):
            raise urllib.error.URLError(ConnectionRefusedError(10061, "connection refused"))

        result = network_preflight.inspect_network(proxies={}, opener=refused)
        self.assertEqual(result["status"], "environment_blocked")
        self.assertEqual(result["reason"], "all_allowed_sources_refused_connection")

    def test_proxy_credentials_never_enter_output(self):
        endpoint = network_preflight.proxy_endpoint(
            {"https": "http://alice:secret@proxy.example:8080"})
        self.assertEqual(endpoint, {"configured": True, "host": "proxy.example", "port": 8080})
        self.assertNotIn("secret", str(endpoint))

    def test_orchestrator_blocks_collection_but_not_completed_release(self):
        with patch.object(orchestrate_daily, "inspect_network", return_value={
            "status": "environment_blocked", "reason": "local_https_proxy_refused"}):
            state = orchestrate_daily.with_network_preflight({"phase": "collection_pending"})
            self.assertEqual(state["phase"], "environment_blocked")
            self.assertIn("Do not classify individual sources", state["next_action"])
        with patch.object(orchestrate_daily, "inspect_network") as probe:
            state = orchestrate_daily.with_network_preflight({"phase": "remote_pending"})
            self.assertEqual(state["phase"], "remote_pending")
            probe.assert_not_called()

    def test_orchestrator_cli_exits_nonzero_for_environment_block(self):
        with patch.object(orchestrate_daily, "inspect", return_value={"phase": "collection_pending"}), \
             patch.object(orchestrate_daily, "inspect_network", return_value={
                 "status": "environment_blocked", "reason": "local_https_proxy_refused"}), \
             patch.object(sys, "argv", ["orchestrate_daily.py", "--date", "2026-09-29",
                                        "--preflight-network"]), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(orchestrate_daily.main(), 2)
        self.assertIn('"phase": "environment_blocked"', output.getvalue())


if __name__ == "__main__":
    unittest.main()
