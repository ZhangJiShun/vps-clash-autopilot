"""Synthetic-only regressions. Never reads installed Clash or contacts a VPS."""
from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import autopilot
from common import SafeError, explicit_path
from profile_ops import apply, build_candidate, inspect_profile, parse_yaml, prepare, validate_node
from runtime_ops import export_mobile, loopback_proxy, share_uri, switch_groups, verify, UnixClient

BASE = (ROOT / 'tests/fixtures/base.yaml').read_bytes()
REQUEST = json.loads((ROOT / 'tests/fixtures/verified-nodes.json').read_text())


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.profile = self.root / 'profile.yaml'
        self.profile.write_bytes(BASE)
        self.nodes = self.root / 'nodes.json'
        self.nodes.write_text(json.dumps(REQUEST))

    def tearDown(self):
        self.temp.cleanup()

    def plan(self):
        return prepare(str(self.profile), str(self.nodes), str(self.root / 'run'))['plan']

    def test_candidate_preserves_rules_dns_original_node_and_comments(self):
        out, summary = build_candidate(BASE, REQUEST)
        old, _, _ = parse_yaml(BASE)
        new, _, _ = parse_yaml(out)
        self.assertEqual(old['rules'], new['rules'])
        self.assertEqual(old['dns'], new['dns'])
        self.assertEqual(old['proxies'][0], new['proxies'][0])
        self.assertIn(b'# Keep this routing comment unchanged.', out)
        self.assertEqual(new['ipv6'], True)
        self.assertEqual(len(new['proxies']), 4)
        self.assertTrue(summary['dns_preserved'])
        self.assertNotIn('DIRECT', new['proxy-groups'][1]['proxies'])

    def test_hy2_hopping_and_obfuscation_rejected_before_export(self):
        for key, value in [('ports', '24443,24444'), ('hop-interval', 5), ('obfs-password', 'fixture')]:
            node = copy.deepcopy(REQUEST['nodes'][1])
            node[key] = value
            with self.assertRaises(SafeError):
                validate_node(node)
            with self.assertRaises(SafeError):
                share_uri(node)

    def test_repeat_is_byte_identical_no_duplicate_nodes(self):
        first, _ = build_candidate(BASE, REQUEST)
        second, summary = build_candidate(first, REQUEST)
        self.assertEqual(first, second)
        self.assertEqual(summary['added_nodes'], [])

    def test_original_outside_changed_blocks_is_preserved(self):
        out, _ = build_candidate(BASE, REQUEST)
        self.assertTrue(out.endswith(BASE[BASE.index(b'# Keep this routing comment'):]))

    def test_flow_style_sequences_supported(self):
        import yaml
        original, _, _ = parse_yaml(BASE)
        text = yaml.safe_dump(original, default_flow_style=True, width=100000)
        out, _ = build_candidate(text.encode(), REQUEST)
        self.assertEqual(len(parse_yaml(out)[0]['proxies']), 4)

    def test_no_final_newline_supported(self):
        out, _ = build_candidate(BASE.rstrip(b'\n'), REQUEST)
        self.assertEqual(parse_yaml(out)[0]['rules'], parse_yaml(BASE)[0]['rules'])

    def test_prepare_only_private_new_artifacts(self):
        plan = self.plan()
        self.assertEqual(self.profile.read_bytes(), BASE)
        for f in Path(plan).parent.iterdir():
            self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual(Path(plan).parent.stat().st_mode & 0o777, 0o700)

    def test_apply_and_exact_rollback(self):
        plan = self.plan()
        self.assertTrue(apply(plan, True)['changed'])
        self.assertFalse(apply(plan, True)['changed'])
        self.assertTrue(apply(plan, True, rollback=True)['changed'])
        self.assertEqual(self.profile.read_bytes(), BASE)

    def test_apply_requires_acknowledgment(self):
        with self.assertRaises(SafeError):
            apply(self.plan(), False)
        self.assertEqual(self.profile.read_bytes(), BASE)

    def test_concurrent_edit_before_apply_is_preserved(self):
        plan = self.plan()
        other = BASE + b'\n# user edit\n'
        self.profile.write_bytes(other)
        with self.assertRaises(SafeError):
            apply(plan, True)
        self.assertEqual(self.profile.read_bytes(), other)

    def test_concurrent_edit_before_rollback_is_preserved(self):
        plan = self.plan()
        apply(plan, True)
        other = self.profile.read_bytes() + b'\n# user edit\n'
        self.profile.write_bytes(other)
        with self.assertRaises(SafeError):
            apply(plan, True, rollback=True)
        self.assertEqual(self.profile.read_bytes(), other)

    def test_tampered_candidate_rejected(self):
        plan = self.plan()
        (Path(plan).parent / 'candidate.yaml').write_bytes(b'proxies: []\n')
        with self.assertRaises(SafeError):
            apply(plan, True)

    def test_semantic_tampering_rejected_even_with_new_hash(self):
        from common import digest
        plan = self.plan()
        c = Path(plan).parent / 'candidate.yaml'
        changed = c.read_bytes().replace(b'MATCH,Proxy', b'MATCH,DIRECT')
        c.write_bytes(changed)
        data = json.loads(Path(plan).read_text())
        data['after_sha256'] = digest(changed)
        Path(plan).write_text(json.dumps(data))
        with self.assertRaises(SafeError):
            apply(plan, True)

    def test_shared_plan_directory_rejected(self):
        plan = self.plan()
        Path(plan).parent.chmod(0o755)
        with self.assertRaises(SafeError):
            apply(plan, True)

    def test_existing_run_directory_not_overwritten(self):
        self.plan()
        with self.assertRaises(SafeError):
            self.plan()

    def test_existing_name_with_different_credentials_rejected(self):
        request = copy.deepcopy(REQUEST)
        request['nodes'][0]['name'] = 'Main'
        with self.assertRaises(SafeError):
            build_candidate(BASE, request)

    def test_unknown_group_stops_without_writing(self):
        request = copy.deepcopy(REQUEST)
        request['groups'] = ['Missing']
        with self.assertRaises(SafeError):
            build_candidate(BASE, request)

    def test_auto_groups_only_selectors_containing_base(self):
        request = copy.deepcopy(REQUEST)
        del request['groups']
        _, summary = build_candidate(BASE, request)
        self.assertEqual(len(summary['groups']), 3)

    def test_duplicate_yaml_key_is_rejected(self):
        with self.assertRaises(SafeError):
            build_candidate(b'ipv6: false\nipv6: true\n' + BASE, REQUEST)

    def test_aliases_are_rejected_not_silently_expanded(self):
        with self.assertRaises(SafeError):
            parse_yaml('a: &alias [1]\nb: *alias\n')

    def test_env_files_not_read(self):
        env = self.root / '.env'
        env.write_text('synthetic-secret')
        with self.assertRaises(SafeError):
            inspect_profile(str(env))

    def test_symlink_profile_rejected(self):
        link = self.root / 'link.yaml'
        link.symlink_to(self.profile)
        with self.assertRaises(SafeError):
            inspect_profile(str(link))

    def test_private_key_rejected_recursively(self):
        n = copy.deepcopy(REQUEST['nodes'][0])
        n['reality-opts']['private-key'] = 'fixture-private'
        with self.assertRaises(SafeError):
            validate_node(n)

    def test_hy2_requires_pin_and_validation(self):
        for field, value in [('fingerprint', ''), ('skip-cert-verify', True), ('port', 65536)]:
            n = copy.deepcopy(REQUEST['nodes'][1])
            n[field] = value
            with self.assertRaises(SafeError):
                validate_node(n)

    def test_ipv6_subnet_is_not_host_address(self):
        n = copy.deepcopy(REQUEST['nodes'][0])
        n['server'] += '/64'
        with self.assertRaises(SafeError):
            validate_node(n)

    def test_inspect_and_cli_error_do_not_echo_secrets(self):
        secret = REQUEST['nodes'][1]['password']
        value, _ = build_candidate(BASE, REQUEST)
        self.profile.write_bytes(value)
        self.assertNotIn(secret, json.dumps(inspect_profile(str(self.profile))))
        self.profile.write_text('password: ["' + secret)
        err = io.StringIO()
        with patch('sys.stderr', err):
            status = autopilot.main(['inspect', '--profile', str(self.profile)])
        self.assertEqual(status, 2)
        self.assertNotIn(secret, err.getvalue())

    def test_mobile_uri_escapes_credentials_and_ipv6(self):
        n = copy.deepcopy(REQUEST['nodes'][2])
        n['password'] = 'fixture:@/?&#+ value'
        uri = share_uri(n)
        parsed = urlsplit(uri)
        self.assertEqual(parsed.hostname, n['server'])
        self.assertEqual(unquote(parsed.username), n['password'])
        query = parse_qs(parsed.query)
        self.assertEqual(query['insecure'], ['0'])
        self.assertEqual(query['pinSHA256'], [n['fingerprint']])

    def test_mobile_offline_artifacts_private_and_html_escaped(self):
        value, _ = build_candidate(BASE, REQUEST)
        data, _, _ = parse_yaml(value)
        data['proxies'][1]['name'] = '<script>alert(1)</script>'
        import yaml
        self.profile.write_text(yaml.safe_dump(data))
        out = self.root / 'mobile'
        report = export_mobile(str(self.profile), str(out), [data['proxies'][1]['name']])
        page = (out / 'scan.html').read_text()
        self.assertIn('&lt;script&gt;', page)
        self.assertNotIn('<script>', page)
        self.assertIn('<svg', page)
        self.assertNotIn('https://', page)
        self.assertFalse(report['network_transmission'])
        for f in out.iterdir():
            self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(SafeError):
            export_mobile(str(self.profile), str(out), None)


class FakeMihomo:
    def __init__(self, fail_group=None, fail_after_apply=False, concurrent=False):
        self.groups = {g: {'type': 'Selector', 'now': 'Main', 'all': ['Main', 'Backup']}
                       for g in ['Proxy', 'ClaudeProxy', 'OpenAIProxy']}
        self.groups.update(Main={'type': 'Vless'}, Backup={'type': 'Hysteria2'})
        self.fail_group, self.fail_after_apply = fail_group, fail_after_apply
        self.failed = False
        self.concurrent = concurrent

    def check(self):
        return {'meta': True, 'version': 'fixture'}

    def request(self, method, path, payload=None):
        if path == '/proxies':
            return {'proxies': copy.deepcopy(self.groups)}
        group = unquote(path.removeprefix('/proxies/'))
        if method == 'GET':
            if self.concurrent and group == 'ClaudeProxy':
                self.groups[group]['now'] = 'Other-user-choice'
                self.concurrent = False
            return copy.deepcopy(self.groups[group])
        if not self.failed and group == self.fail_group:
            self.failed = True
            if self.fail_after_apply:
                self.groups[group]['now'] = payload['name']
            raise SafeError('synthetic request failure')
        self.groups[group]['now'] = payload['name']


class RuntimeTests(unittest.TestCase):
    groups = ['Proxy', 'ClaudeProxy', 'OpenAIProxy']

    def test_switch_all_three_and_readback(self):
        c = FakeMihomo()
        r = switch_groups('unused', 'Backup', self.groups, True, client=c)
        self.assertTrue(r['readback_verified'])
        self.assertTrue(all(c.groups[g]['now'] == 'Backup' for g in self.groups))

    def test_preflight_checks_every_group_before_any_write(self):
        c = FakeMihomo()
        c.groups['OpenAIProxy']['all'] = ['Main']
        with self.assertRaises(SafeError):
            switch_groups('unused', 'Backup', self.groups, True, client=c)
        self.assertEqual(c.groups['Proxy']['now'], 'Main')

    def test_switch_midway_failure_restores(self):
        for ambiguous in [False, True]:
            c = FakeMihomo('ClaudeProxy', ambiguous)
            with self.assertRaises(SafeError):
                switch_groups('unused', 'Backup', self.groups, True, client=c)
            self.assertTrue(all(c.groups[g]['now'] == 'Main' for g in self.groups))

    def test_concurrent_switch_preserves_user_choice(self):
        c = FakeMihomo(concurrent=True)
        with self.assertRaises(SafeError):
            switch_groups('unused', 'Backup', self.groups, True, client=c)
        self.assertEqual(c.groups['Proxy']['now'], 'Main')
        self.assertEqual(c.groups['ClaudeProxy']['now'], 'Other-user-choice')

    def test_switch_requires_ack_and_leaf(self):
        for node, approve in [('Backup', False), ('Proxy', True), ('DIRECT', True)]:
            with self.assertRaises(SafeError):
                switch_groups('unused', node, self.groups, approve, client=FakeMihomo())

    def test_only_loopback_proxy_urls(self):
        for p in ['http://192.0.2.1:80', 'http://u:p@127.0.0.1:7897', 'http://127.0.0.1:80/path', 'https://127.0.0.1:80']:
            with self.assertRaises(SafeError):
                loopback_proxy(p)
        self.assertEqual(loopback_proxy('http://[::1]:7897'), 'http://[::1]:7897')

    def test_verify_403_not_acceptance_and_no_proxy_env_ambiguity(self):
        commands = []
        def runner(cmd, **kwargs):
            commands.append(cmd)
            status = '204' if 'google.com' in cmd[-1] else '200' if 'youtube.com' in cmd[-1] else '403'
            return SimpleNamespace(returncode=0, stdout=status, stderr='hidden')
        report = verify(None, 3, None, runner=runner)
        self.assertTrue(report['google_repeated_pass'])
        self.assertFalse(report['results'][-1]['http_status_2xx'])
        self.assertFalse(report['node_routing_verified'])
        self.assertEqual(report['browser_acceptance'], 'not-run')
        self.assertTrue(all(c[1] == '-q' and c[c.index('--noproxy') + 1] == '*' for c in commands))

    def test_redirect_is_not_content_acceptance(self):
        report = verify(None, 3, None, runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout='302', stderr=''))
        self.assertTrue(all(r['http_response_received'] for r in report['results']))
        self.assertTrue(all(not r['http_status_2xx'] for r in report['results']))
        self.assertFalse(report['google_repeated_pass'])

    def test_verify_timeout_does_not_claim_success(self):
        report = verify(None, 3, None, runner=lambda *a, **k: SimpleNamespace(returncode=28, stdout='000', stderr='fixture'))
        self.assertFalse(report['google_repeated_pass'])
        self.assertTrue(all(not r['http_response_received'] for r in report['results']))

    def test_verify_repetition_bounds(self):
        for count in [0, 1, 2, 11]:
            with self.assertRaises(SafeError):
                verify(None, count, None)

    def test_real_unix_socket_does_not_allow_other_mutation_routes(self):
        with tempfile.TemporaryDirectory() as root:
            p = Path(root) / 'fixture.sock'
            sock = socket.socket(socket.AF_UNIX)
            sock.bind(str(p))
            try:
                api = UnixClient(str(p))
                for method, path in [('DELETE', '/connections'), ('PUT', '/configs'), ('GET', '/secret')]:
                    with self.assertRaises(SafeError):
                        api.request(method, path)
            finally:
                sock.close()


if __name__ == '__main__':
    unittest.main()
