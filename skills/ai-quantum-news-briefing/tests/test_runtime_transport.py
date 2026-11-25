"""Non-secret runtime wiring and HeadObject boundaries; all OSS calls mocked."""
import json
import io
from contextlib import redirect_stdout, redirect_stderr
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_runtime as runtime
import publish_daily_to_oss as publisher


class RuntimeTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.program = self.root / 'ossutil.exe'
        self.profile_container = self.root / 'fixture.ini'
        self.program.write_bytes(b'fixture, never executed')
        self.profile_container.write_bytes(b'fixture, never read')
        self.runtime_path = self.root / 'runtime.json'
        self.settings = {'version': 1, 'python_executable': sys.executable,
            'ossutil_executable': str(self.program), 'ossutil_config': str(self.profile_container),
            'ossutil_endpoint': 'https://oss-cn-hongkong.aliyuncs.com'}
        self.runtime_path.write_text(json.dumps(self.settings), encoding='utf-8')
        self.routing_path = self.root / 'news_publish.local.json'
        self.routing = {'site_index_url': 'https://example.org/index.html', 'bucket': 'example-bucket',
            'region': 'cn-hongkong', 'object_prefix': '', 'ossutil_profile': 'fixture'}
        self.routing_path.write_text(json.dumps(self.routing), encoding='utf-8')
        clean = patch.dict(os.environ, {key: '' for key in runtime.ENV_KEYS.values()})
        clean.start(); self.addCleanup(clean.stop)
        os.environ.pop('PAPERTRACE_OSSUTIL_EXECUTABLE', None)

    def test_runtime_never_reads_profile_container(self):
        raw = self.runtime_path.read_text(encoding='utf-8')
        def read(path, *args, **kwargs):
            self.assertEqual(path, self.runtime_path)
            return raw
        with patch.object(Path, 'read_text', read):
            self.assertEqual(runtime.load_runtime(self.runtime_path), self.settings)

    def test_scope_restores_environment_even_on_failure(self):
        original_path = os.environ.get('PATH')
        original = {key: os.environ.get(key) for key in runtime.ENV_KEYS.values()}
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with runtime.runtime_scope(self.runtime_path):
                self.assertEqual(os.environ['PAPERTRACE_OSSUTIL_CONFIG'], str(self.profile_container))
                raise RuntimeError('fixture')
        self.assertEqual({key: os.environ.get(key) for key in runtime.ENV_KEYS.values()}, original)
        self.assertEqual(os.environ.get('PATH'), original_path)

    def test_unknown_fields_boolean_version_and_missing_program_rejected(self):
        for change in ({'version': True}, {'version': 2}, {'unsupported': 'field'},
                       {'ossutil_executable': str(self.root / 'absent.exe')}):
            with self.subTest(change=change):
                self.runtime_path.write_text(json.dumps({**self.settings, **change}), encoding='utf-8')
                with self.assertRaises(ValueError): runtime.load_runtime(self.runtime_path)

    def test_head_only_is_read_only_and_explicit_without_acl(self):
        identity = publisher.deployment_id(self.routing)
        response = SimpleNamespace(returncode=0, stdout='metadata', stderr='')
        with runtime.runtime_scope(self.runtime_path), \
             patch.object(publisher.shutil, 'which', return_value=str(self.program)), \
             patch.object(publisher.subprocess, 'run', return_value=response) as command, \
             patch.object(publisher, 'checked_site') as site, \
             patch.object(publisher, 'check_bucket_binding') as binding, \
             patch.object(publisher, 'upload_file') as upload:
            result = publisher.doctor(self.routing_path, head_only=True)
        argv = command.call_args.args[0]
        self.assertEqual(argv[:3], [str(self.program), 'api', 'head-object'])
        for flag, value in (('--config-file', str(self.profile_container)), ('--profile', 'fixture'),
                            ('--region', 'cn-hongkong'), ('--endpoint', self.settings['ossutil_endpoint'])):
            self.assertEqual(argv[argv.index(flag)+1], value)
        self.assertNotIn('stat', argv)
        self.assertNotIn('get-object-acl', argv)
        self.assertEqual(result['upload_status'], 'not_tested')
        self.assertEqual(result['bucket_binding_status'], 'not_checked')
        self.assertEqual(publisher.deployment_id(self.routing), identity)
        site.assert_not_called(); binding.assert_not_called(); upload.assert_not_called()
        self.assertFalse((self.root / 'news').exists())

    def test_head_connection_error_is_not_credential_expiry(self):
        response = SimpleNamespace(returncode=3, stdout='', stderr='dial tcp: connectex: forbidden; sensitive-marker')
        with patch.object(publisher.subprocess, 'run', return_value=response):
            result = publisher.head_bucket_index(self.routing)
        self.assertEqual(result['code'], 'oss_connection_environment_blocked')
        self.assertNotIn('sensitive-marker', json.dumps(result))

    def test_native_proxy_selector_uses_no_proxy_values_in_arguments(self):
        for name in ('HTTP_PROXY', 'HTTPS_PROXY'):
            with self.subTest(name=name), patch.dict(os.environ):
                os.environ.pop('HTTP_PROXY', None); os.environ.pop('HTTPS_PROXY', None)
                os.environ[name] = 'http://fixture-user:fixture-password@fixture-proxy:3128'
                os.environ['NO_PROXY'] = 'fixture-internal'
                before = dict(os.environ)
                with runtime.runtime_scope(self.runtime_path):
                    command = publisher.ossutil_command(self.routing, ['api', 'head-object'])
                self.assertEqual(command[-2:], ['--proxy', 'env'])
                self.assertNotIn('fixture-password', json.dumps(command))
                self.assertNotIn('fixture-proxy', json.dumps(command))
                self.assertNotIn('--skip-verify-cert', command)
                self.assertEqual(dict(os.environ), before)

    def test_no_http_proxy_preserves_ordinary_terminal_command(self):
        with patch.dict(os.environ):
            for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'):
                os.environ.pop(name, None)
            with runtime.runtime_scope(self.runtime_path):
                command = publisher.ossutil_command(self.routing, ['api', 'head-object'])
            self.assertNotIn('--proxy', command)

    def test_proxy_failure_has_no_direct_retry(self):
        before = dict(os.environ)
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://fixture-proxy:3128'}), \
             patch.object(publisher.subprocess, 'run', return_value=SimpleNamespace(
                 returncode=3, stdout='', stderr='proxyconnect tcp: policy denied')) as send:
            value = publisher.head_bucket_index(self.routing)
        self.assertEqual(value['status'], 'blocked')
        self.assertEqual(value['code'], 'oss_connection_environment_blocked')
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0][-2:], ['--proxy', 'env'])
        self.assertEqual(dict(os.environ), before)

    def test_cli_runtime_scope_is_read_only_and_restored(self):
        output = io.StringIO()
        previous = {name: os.environ.get(name) for name in runtime.ENV_KEYS.values()}
        with redirect_stdout(output), patch.object(publisher.shutil, 'which', return_value=str(self.program)), \
             patch.object(publisher.subprocess, 'run', return_value=SimpleNamespace(returncode=0,stdout='',stderr='')) as command:
            code = publisher.main(['doctor','--head-only','--config',str(self.routing_path),
                                   '--runtime-config',str(self.runtime_path)])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(output.getvalue())['upload_status'],'not_tested')
        self.assertEqual(command.call_args.args[0][0],str(self.program))
        self.assertEqual({name: os.environ.get(name) for name in runtime.ENV_KEYS.values()},previous)

    def test_head_only_flag_cannot_authorize_publish(self):
        with redirect_stderr(io.StringIO()), patch.object(publisher,'publish') as send:
            with self.assertRaises(SystemExit) as error:
                publisher.main(['publish','--head-only'])
        self.assertEqual(error.exception.code,2)
        send.assert_not_called()

    def test_head_access_denied_is_scoped_to_head_object(self):
        response = SimpleNamespace(returncode=1, stdout='', stderr='AccessDenied 403 sensitive-marker')
        with patch.object(publisher.subprocess, 'run', return_value=response):
            result = publisher.head_bucket_index(self.routing)
        self.assertEqual(result['code'], 'head_object_access_denied')
        self.assertNotIn('sensitive-marker', json.dumps(result))

    def test_endpoint_mismatch_stops_before_signed_request(self):
        for endpoint in ('https://untrusted.example', 'https://oss-cn-shanghai.aliyuncs.com',
                         'http://oss-cn-hongkong.aliyuncs.com'):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {'PAPERTRACE_OSSUTIL_ENDPOINT': endpoint}), \
                 patch.object(publisher.subprocess, 'run') as transport:
                with self.assertRaises(publisher.PublishError) as error:
                    publisher.head_bucket_index(self.routing)
                self.assertEqual(error.exception.code, 'oss_endpoint_mismatch')
                transport.assert_not_called()

    def test_real_bucket_content_binding_is_still_required(self):
        with patch.object(publisher, 'read_bucket_index', return_value=b'different'):
            with self.assertRaises(publisher.PublishError) as error:
                publisher.check_bucket_binding(self.routing, b'website')
        self.assertEqual(error.exception.code, 'deployment_mismatch')

    def test_formal_upload_and_preview_commands_use_the_same_transport(self):
        source = self.root / 'page.html'; source.write_text('fixture', encoding='utf-8')
        response = SimpleNamespace(returncode=0, stdout='', stderr='')
        with runtime.runtime_scope(self.runtime_path), \
             patch.object(publisher.subprocess, 'run', return_value=response) as transport:
            publisher.upload_file(self.routing, source, 'index.html')
            argv = transport.call_args.args[0]
            self.assertEqual(argv[0], str(self.program))
            self.assertIn('--config-file', argv); self.assertIn('--endpoint', argv)
        # Pure command construction/mocked transport only. The real Bucket
        # versioning prerequisite remains fail-closed for previews.
        with runtime.runtime_scope(self.runtime_path), patch.object(publisher.subprocess, 'run',
                return_value=SimpleNamespace(returncode=1, stdout='', stderr='403')) as transport:
            with self.assertRaises(publisher.PublishError) as error:
                publisher.check_preview_overwrite_safety(self.routing)
            self.assertEqual(error.exception.code, 'preview_storage_unverified')
            self.assertIn('get-bucket-versioning', transport.call_args.args[0])

    def test_connection_stages_do_not_conflate_cloud_and_local_errors(self):
        for error, stage in (
            ('dial tcp: lookup endpoint: no such host', 'dns'),
            ('proxyconnect tcp: connectex: refused', 'proxy'),
            ('x509: certificate signed by unknown authority', 'tls'),
            ('dial tcp 1.2.3.4:443: connectex: forbidden by its access permissions', 'tcp_connect'),
            ('StatusCode: 403 AccessDenied', 'cloud_http'),
            ('request timeout', 'timeout_stage_unknown'),
        ):
            with self.subTest(error=error):
                value = publisher._connection_details(error)
                self.assertEqual(value['connection_stage'], stage)
                self.assertFalse(value['cloud_authentication_verified'])
        self.assertTrue(publisher._connection_details('connectex: 10013')['socket_permission_denied'])
        self.assertEqual(publisher._connection_details('StatusCode: 403')['http_status'], 403)

    def test_detailed_errors_redact_credentials_queries_and_proxy_values(self):
        raw = ('dial tcp: connectex: forbidden by its access permissions\n'
               'https://alice:password-marker@example.org/index.html?Signature=query-marker\n'
               'Authorization: OSS access-marker:signature-marker\n'
               '{"AccessKeySecret": "json-marker"}\n'
               '<SecurityToken>xml-marker</SecurityToken>\n'
               'SecurityToken=token-marker;\n'
               'proxyconnect http://proxy-user:proxy-pass@proxy.fixture:8080 proxy.fixture\n'
               'environment-secret-marker')
        with patch.dict(os.environ, {'HTTPS_PROXY': 'http://proxy-user:proxy-pass@proxy.fixture:8080',
                                     'FIXTURE_API_KEY': 'environment-secret-marker'}):
            safe = publisher._safe_connection_error(raw)
        for forbidden in ('alice', 'password-marker', 'query-marker', 'access-marker',
                          'signature-marker', 'json-marker', 'xml-marker', 'token-marker',
                          'proxy-user', 'proxy-pass', 'proxy.fixture', 'environment-secret-marker'):
            self.assertNotIn(forbidden, safe)
        self.assertIn('forbidden by its access permissions', safe)
        self.assertIn('example.org/index.html', safe)
        with patch.dict(os.environ, {'HTTPS_PROXY': 'https://[malformed-proxy'}):
            self.assertNotIn('malformed-proxy', publisher._safe_connection_error('https://[malformed-proxy'))

    def test_detailed_cli_preserves_child_exit_and_restores_process(self):
        before = dict(os.environ)
        output = io.StringIO()
        response = SimpleNamespace(returncode=3, stdout='', stderr='dial tcp: connectex: 10013')
        with redirect_stdout(output), patch.object(publisher.subprocess, 'run', return_value=response) as send, \
             patch.object(publisher, 'checked_site') as site, patch.object(publisher, 'upload_file') as upload:
            code = publisher.main(['doctor', '--head-only', '--connection-details',
                                  '--config', str(self.routing_path), '--runtime-config', str(self.runtime_path)])
        value = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(value['exit_code'], 3)
        self.assertEqual(value['diagnostic']['connection_stage'], 'tcp_connect')
        self.assertEqual(value['diagnostic']['python_executable'], sys.executable)
        self.assertIn('started_utc', value['diagnostic'])
        self.assertEqual(value['diagnostic']['command'][1:3], ['api', 'head-object'])
        send.assert_called_once(); site.assert_not_called(); upload.assert_not_called()
        self.assertEqual(dict(os.environ), before)

    def test_detailed_flag_cannot_authorize_publish(self):
        with redirect_stderr(io.StringIO()), patch.object(publisher, 'publish') as send:
            with self.assertRaises(SystemExit) as caught:
                publisher.main(['publish', '--connection-details'])
        self.assertEqual(caught.exception.code, 2)
        send.assert_not_called()

    def test_taskbox_direct_python_runtime_is_scoped_and_restored(self):
        import taskbox_daily as taskbox
        before = dict(os.environ)
        def action(args):
            self.assertEqual(os.environ['PAPERTRACE_OSSUTIL_EXECUTABLE'], str(self.program))
            self.assertEqual(os.environ['PAPERTRACE_OSSUTIL_CONFIG'], str(self.profile_container))
            raise RuntimeError('synthetic action failure')
        with patch.object(taskbox, 'execute', side_effect=action):
            with self.assertRaisesRegex(RuntimeError, 'synthetic action failure'):
                taskbox.main(['next', '--date', '2026-10-25', '--runtime-config', str(self.runtime_path)])
        self.assertEqual(dict(os.environ), before)

    def test_taskbox_bad_runtime_blocks_before_action(self):
        import taskbox_daily as taskbox
        output = io.StringIO()
        with redirect_stdout(output), patch.object(taskbox, 'execute') as action:
            code = taskbox.main(['next', '--date', '2026-10-25',
                                 '--runtime-config', str(self.root / 'missing.json')])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())['code'], 'runtime_configuration_unavailable')
        action.assert_not_called()


if __name__ == '__main__': unittest.main()
