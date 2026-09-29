"""Read-only, fail-closed network preflight for scheduled daily collection.

This checks the command's *effective* network path, not whether a config file
exists. It does not establish source coverage or OSS upload permission.
"""

from __future__ import annotations

import argparse
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable


CANARIES = {
    "aps": "https://feeds.aps.org/rss/recent/pra.xml",
    "ai_hot": "https://aihot.virxact.com/feed.xml",
}
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def proxy_endpoint(proxies: dict[str, str] | None = None) -> dict[str, Any]:
    """Return only a proxy host/port; never expose userinfo or a proxy URL."""
    values = urllib.request.getproxies() if proxies is None else proxies
    raw = values.get("https") or values.get("HTTPS") or ""
    if not raw:
        return {"configured": False, "host": None, "port": None}
    try:
        parsed = urllib.parse.urlsplit(raw if "://" in raw else "http://" + raw)
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return {"configured": True, "host": parsed.hostname, "port": port}
    except ValueError:
        return {"configured": True, "host": None, "port": None}


def _probe(name: str, url: str, timeout: float,
           opener: Callable[..., Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "PaperTrace-network-preflight/1.0"})
    try:
        with opener(request, timeout=timeout) as response:
            return {"name": name, "result": "http_response", "http_status": int(response.status)}
    except urllib.error.HTTPError as exc:
        exc.close()
        return {"name": name, "result": "http_response", "http_status": int(exc.code)}
    except urllib.error.URLError as exc:
        reason = exc.reason
        kind = ("connection_refused" if isinstance(reason, ConnectionRefusedError) else
                "timeout" if isinstance(reason, TimeoutError) else type(reason).__name__)
        return {"name": name, "result": "transport_error", "error_kind": kind}
    except (OSError, ValueError) as exc:
        kind = ("connection_refused" if isinstance(exc, ConnectionRefusedError) else
                "timeout" if isinstance(exc, TimeoutError) else type(exc).__name__)
        return {"name": name, "result": "transport_error", "error_kind": kind}


def inspect_network(*, timeout: float = 8.0, proxies: dict[str, str] | None = None,
                    connector: Callable[..., Any] = socket.create_connection,
                    opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    """Classify a shared environment fault without blaming individual sources."""
    proxy = proxy_endpoint(proxies)
    result: dict[str, Any] = {"status": "unverified", "proxy": proxy, "probes": [],
                              "policy_enforcement": "not_verified"}
    if proxy["configured"] and proxy["host"] in LOOPBACK_HOSTS and proxy["port"]:
        try:
            connection = connector((proxy["host"], proxy["port"]), timeout=1.0)
            connection.close()
        except ConnectionRefusedError:
            result.update(status="environment_blocked", reason="local_https_proxy_refused")
            return result
        except (TimeoutError, socket.timeout):
            result.update(status="environment_blocked", reason="local_https_proxy_unreachable")
            return result
        except (OSError, ValueError) as exc:
            result.update(status="environment_unverified", reason=type(exc).__name__)
            return result
    elif proxy["configured"] and (not proxy["host"] or not proxy["port"]):
        result.update(status="environment_unverified", reason="https_proxy_invalid")
        return result

    result["probes"] = [_probe(name, url, timeout, opener) for name, url in CANARIES.items()]
    if any(row["result"] == "http_response" for row in result["probes"]):
        result.update(status="ready", reason="at_least_one_allowed_source_replied")
    elif all(row.get("error_kind") == "connection_refused" for row in result["probes"]):
        result.update(status="environment_blocked", reason="all_allowed_sources_refused_connection")
    else:
        result.update(status="environment_unverified", reason="allowed_sources_not_confirmed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()
    if not 0 < args.timeout <= 30:
        parser.error("--timeout must be greater than 0 and at most 30 seconds")
    result = inspect_network(timeout=args.timeout)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
