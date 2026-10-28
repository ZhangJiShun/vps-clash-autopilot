"""Documented Mihomo Unix-socket operations, bounded probes and offline exports."""
from __future__ import annotations

SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by the explicit autopilot CLI; not a standalone command."

import html
import http.client
import io
import ipaddress
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
from urllib.parse import quote, urlencode, urlsplit

from common import SafeError, explicit_path, new_private_dir, private_file, private_json, read_bytes
from profile_ops import parse_yaml, validate_node


class UnixClient:
    """Never opens a TCP controller or obtains browser/SSH credentials."""
    def __init__(self, path: str):
        self.path = explicit_path(path)
        st = self.path.stat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid not in {0, os.getuid()}:
            raise SafeError('Select a real Mihomo Unix socket owned by you or root.')

    def request(self, method: str, path: str, payload=None):
        class Connection(http.client.HTTPConnection):
            def connect(inner):
                inner.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                inner.sock.settimeout(5)
                inner.sock.connect(str(self.path))
        if method == 'GET' and path not in {'/version', '/configs', '/proxies', '/connections', '/rules'} and not path.startswith('/proxies/'):
            raise SafeError('Unsupported read-only API route.')
        if method != 'GET' and not (method == 'PUT' and path.startswith('/proxies/')):
            raise SafeError('Only selector changes are permitted by this helper.')
        client = Connection('localhost', timeout=5)
        try:
            body = json.dumps(payload) if payload is not None else None
            client.request(method, path, body, {'Content-Type': 'application/json'})
            response = client.getresponse()
            raw = response.read(4 * 1024 * 1024 + 1)
            if response.status not in {200, 204} or len(raw) > 4 * 1024 * 1024:
                raise SafeError('Mihomo API rejected a request; inspect target state before retrying.')
            return json.loads(raw) if raw else None
        except (ValueError, OSError, http.client.HTTPException):
            raise SafeError('Cannot read Mihomo API state; response details withheld.') from None
        finally:
            client.close()

    def check(self):
        v = self.request('GET', '/version')
        if not isinstance(v, dict) or v.get('meta') is not True:
            raise SafeError('The specified socket is not an identified Mihomo runtime.')
        return v


def switch_groups(path: str, node: str, groups: list[str], approved: bool, *, client=None):
    if not approved:
        raise SafeError('Switch requires target-scoped authorization and --approve.')
    if not groups or len(set(groups)) != len(groups):
        raise SafeError('Specify a nonempty unique group list.')
    api = client or UnixClient(path)
    api.check()
    all_proxies = api.request('GET', '/proxies')['proxies']
    target = all_proxies.get(node, {})
    if not target or target.get('type') in {'Selector', 'URLTest', 'Fallback', 'LoadBalance', 'Direct', 'Reject'}:
        raise SafeError('Choose an explicit leaf proxy, not another group or DIRECT.')
    original = {}
    for group in groups:
        data = all_proxies.get(group, {})
        if data.get('type') != 'Selector' or node not in data.get('all', []) or data.get('now') not in data.get('all', []):
            raise SafeError('Every selected group must be a valid selector containing the target.')
        original[group] = data['now']
    attempted = []
    try:
        for group in groups:
            if original[group] == node:
                continue
            # Compare before each write to preserve concurrent UI/user changes.
            route = '/proxies/' + quote(group, safe='')
            if api.request('GET', route).get('now') != original[group]:
                raise SafeError('Group changed concurrently; stopping the switch.')
            attempted.append(group)
            api.request('PUT', route, {'name': node})
            if api.request('GET', route).get('now') != node:
                raise SafeError('Selector readback failed.')
        snapshot = api.request('GET', '/proxies')['proxies']
        if any(snapshot[g].get('now') != node for g in groups):
            raise SafeError('Final selector readback failed.')
    except Exception as error:
        incomplete = []
        for group in reversed(attempted):
            route = '/proxies/' + quote(group, safe='')
            try:
                current = api.request('GET', route).get('now')
                if current == node:
                    api.request('PUT', route, {'name': original[group]})
                    if api.request('GET', route).get('now') != original[group]:
                        incomplete.append(group)
                elif current != original[group]:
                    incomplete.append(group)  # Do not overwrite a third-party change.
            except Exception:
                incomplete.append(group)
        if incomplete:
            raise SafeError('Switch failed; recovery incomplete or concurrent edits detected. Re-read groups before any retry.') from None
        raise SafeError('Switch failed; changed selectors were restored. Re-read state before retrying.') from None
    return {'selected_node': node, 'groups': groups, 'previous': original,
            'readback_verified': True, 'existing_connections_may_keep_old_route': True}


ENDPOINTS = {
    'google': 'https://www.google.com/generate_204',
    'youtube': 'https://www.youtube.com/',
    'chatgpt': 'https://chatgpt.com/',
}


def loopback_proxy(value: str) -> str:
    try:
        p = urlsplit(value)
        host = ipaddress.ip_address(p.hostname or '')
        valid = (p.scheme == 'http' and host.is_loopback and p.port is not None
                 and not p.username and not p.password and p.path in {'', '/'}
                 and not p.query and not p.fragment)
    except ValueError:
        valid = False
    if not valid:
        raise SafeError('Explicit proxy must be an HTTP loopback IP and port, without credentials.')
    return value


def verify(proxy: str | None, repeats: int, output: str | None, *, runner=subprocess.run):
    if not 3 <= repeats <= 10:
        raise SafeError('Use 3 to 10 repeated Google probes.')
    if proxy:
        loopback_proxy(proxy)
    # No curlrc, no environment-proxy ambiguity, no cookies or response-body logs.
    common = ['curl', '-q', '--proto', '=https', '--connect-timeout', '8', '--max-time', '15',
              '--max-redirs', '0', '-I', '-sS', '-o', os.devnull, '-w', '%{http_code}']
    common += ['--proxy', proxy, '--noproxy', ''] if proxy else ['--noproxy', '*']
    results = []
    for site in ['google'] * repeats + ['youtube', 'chatgpt']:
        r = runner(common + [ENDPOINTS[site]], capture_output=True, text=True, timeout=20)
        raw = r.stdout.strip()
        code = int(raw) if raw.isdigit() and len(raw) == 3 else 0
        results.append({'site': site, 'exit_code': r.returncode, 'http_status': code,
                        'http_response_received': r.returncode == 0 and 100 <= code <= 599,
                        'http_status_2xx': r.returncode == 0 and 200 <= code < 300})
    google = [x for x in results if x['site'] == 'google']
    report = {'mode': 'explicit-local-proxy' if proxy else 'system-path-no-proxy',
              'google_repeated_pass': all(x['exit_code'] == 0 and x['http_status'] == 204 for x in google),
              'results': results, 'node_routing_verified': False,
              'browser_acceptance': 'not-run', 'mobile_acceptance': 'not-run',
              'note': 'Correlate runtime chains/logs and actual TUN ownership. HTTP 403 is a response, not usable ChatGPT acceptance.'}
    if output:
        file = explicit_path(output)
        if file.parent.stat().st_mode & 0o077:
            raise SafeError('Store reports in a private run directory (0700).')
        private_json(file, report)
    return report


def share_uri(node: dict) -> str:
    validate_node(node)
    host = '[' + node['server'] + ']' if ':' in node['server'] else node['server']
    if node['type'] == 'vless':
        reality = node['reality-opts']
        query = {'encryption': 'none', 'security': 'reality', 'type': 'tcp',
                 'flow': node['flow'], 'sni': node['servername'], 'fp': node['client-fingerprint'],
                 'pbk': reality['public-key'], 'sid': reality.get('short-id', '')}
        uri = 'vless://' + quote(node['uuid'], safe='') + '@' + host + ':' + str(node['port']) + '?'
    else:
        query = {'sni': node['sni'], 'insecure': '0',
                 'pinSHA256': node['fingerprint'].replace(':', ''), 'alpn': 'h3'}
        uri = 'hysteria2://' + quote(node['password'], safe='') + '@' + host + ':' + str(node['port']) + '/?'
    return uri + urlencode(query) + '#' + quote(node['name'], safe='')


def export_mobile(profile: str, output_dir: str, names: list[str] | None):
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        raise SafeError('Offline QR dependency missing. Install declared requirements in an isolated environment first.') from None
    value, _, _ = parse_yaml(read_bytes(profile))
    nodes = value.get('proxies', [])
    if names:
        nodes = [n for n in nodes if n.get('name') in names]
        if {n.get('name') for n in nodes} != set(names):
            raise SafeError('Some requested mobile nodes are absent.')
    else:
        nodes = [n for n in nodes if n.get('type') in {'vless', 'hysteria2'}]
    if not nodes:
        raise SafeError('No supported nodes to export.')
    # Validate and render everything before creating any output artifacts.
    rendered = []
    for n in nodes:
        uri = share_uri(n)
        image = qrcode.make(uri, image_factory=SvgPathImage, border=4)
        buffer = io.BytesIO()
        image.save(buffer)
        rendered.append((n['name'], uri, buffer.getvalue()))
    out = new_private_dir(output_dir)
    page = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width"><title>Private node import</title>',
            '<style>body{font:18px system-ui;max-width:760px;margin:2rem auto;padding:1rem}section{margin:2rem 0}svg{width:100%;max-width:600px;height:auto}</style>',
            '<h1>离线节点导入 / Offline node import</h1>',
            '<p>二维码和链接含登录凭据，仅自己使用。保留原节点与分流规则。手机未实测。</p>',
            '<p>HY2 必须保留证书 SHA-256 固定指纹。证书错误先检查客户端兼容性，不要直接关闭验证。</p>']
    text = []
    for i, (name, uri, svg) in enumerate(rendered, 1):
        private_file(out / f'node-{i}.svg', svg)
        vector = svg.decode('utf-8')
        vector = vector[vector.index('<svg'):]
        page.append('<section><h2>' + html.escape(name) + '</h2>' + vector + '</section>')
        text.extend([name, uri, ''])
    page.append('</html>')
    private_file(out / 'scan.html', '\n'.join(page).encode())
    private_file(out / 'nodes.txt', '\n'.join(text).encode())
    return {'node_count': len(rendered), 'page': str(out / 'scan.html'),
            'links': str(out / 'nodes.txt'), 'contains_credentials': True,
            'mobile_acceptance': 'not-run', 'network_transmission': False}
