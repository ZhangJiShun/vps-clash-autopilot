"""Conservative, hash-bound edits to explicitly selected Clash YAML files."""
from __future__ import annotations

SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by the explicit autopilot CLI; not a standalone command."

import copy
import ipaddress
import json
from pathlib import Path
import re

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode
from yaml.tokens import AliasToken, AnchorToken

from common import (SafeError, atomic_replace, digest, explicit_path, new_private_dir,
                    private_file, private_json, read_bytes, read_json)


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError:
            raise SafeError('Unsupported YAML mapping key.') from None
        if duplicate:
            raise SafeError('Duplicate YAML keys are ambiguous; no changes made.')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse_yaml(data: bytes | str) -> tuple[dict, MappingNode, str]:
    try:
        text = data.decode('utf-8') if isinstance(data, bytes) else data
        if any(isinstance(t, (AliasToken, AnchorToken)) for t in yaml.scan(text)):
            raise SafeError('YAML anchors/aliases require a reviewed adapter; no changes made.')
        value = yaml.load(text, Loader=UniqueLoader)
        tree = yaml.compose(text)
    except (yaml.YAMLError, UnicodeError):
        raise SafeError('Invalid YAML; details withheld to protect credentials.') from None
    if not isinstance(value, dict) or not isinstance(tree, MappingNode):
        raise SafeError('Expected one Clash YAML mapping.')
    return value, tree, text


def _field(tree: MappingNode, name: str):
    return next((v for k, v in tree.value if k.value == name), None)


def _name(value) -> str:
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\x00'):
        raise SafeError('Node/group names must be nonempty single-line strings.')
    if len(value) > 128:
        raise SafeError('Node/group name is too long.')
    return value


def validate_node(node: dict) -> None:
    if not isinstance(node, dict):
        raise SafeError('Each node must be a mapping.')
    _name(node.get('name'))
    # Server keys must never enter a client export, at any nesting level.
    def check(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower().replace('_', '-') in {'private-key', 'privatekey', 'key-file', 'keyfile'}:
                    raise SafeError('Server private-key fields are forbidden in client input.')
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)
    check(node)
    if not isinstance(node.get('server'), str) or not node['server'] or any(c.isspace() for c in node['server']):
        raise SafeError('Node needs a server address without whitespace.')
    try:
        ipaddress.ip_address(node['server'])
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9.-]+', node['server']) or ':' in node['server']:
            raise SafeError('Use a plain DNS hostname or an unbracketed IP address.')
    if type(node.get('port')) is not int or not 1 <= node['port'] <= 65535:
        raise SafeError('Node port must be an integer from 1 to 65535.')
    if node.get('type') == 'vless':
        import uuid
        try:
            uuid.UUID(node.get('uuid', ''))
        except (ValueError, AttributeError, TypeError):
            raise SafeError('VLESS needs a valid UUID.') from None
        r = node.get('reality-opts', {})
        if (node.get('tls') is not True or node.get('network', 'tcp') != 'tcp'
                or node.get('flow') != 'xtls-rprx-vision'
                or not node.get('servername') or not node.get('client-fingerprint')
                or not isinstance(r, dict)
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', str(r.get('public-key', '')))
                or not re.fullmatch(r'(?:[0-9a-fA-F]{2}){0,8}', str(r.get('short-id', '')))):
            raise SafeError('VLESS Reality fields are missing or malformed.')
    elif node.get('type') == 'hysteria2':
        pin = node.get('fingerprint', '').replace(':', '')
        if (not isinstance(node.get('password'), str) or not node['password']
                or node.get('skip-cert-verify', False) is not False
                or not re.fullmatch(r'[A-Fa-f0-9]{64}', pin) or not node.get('sni')):
            raise SafeError('HY2 requires authentication, SNI and an exact SHA256 certificate pin; skip-cert-verify must be false.')
        if any(node.get(k) for k in ('obfs', 'obfs-password', 'ports', 'hop-interval')):
            raise SafeError('The initial HY2 baseline excludes obfuscation and port hopping.')
    else:
        raise SafeError('Only VLESS Reality and Hysteria2 additions are supported.')


def _validated_profile(value: dict) -> None:
    nodes = value.get('proxies')
    groups = value.get('proxy-groups')
    if not isinstance(nodes, list) or not nodes or not isinstance(groups, list):
        raise SafeError('Expected explicit proxies and proxy-groups; provider-only profiles need an adapter.')
    all_names = []
    for entry in nodes + groups:
        if not isinstance(entry, dict):
            raise SafeError('Invalid proxy/group entry.')
        all_names.append(_name(entry.get('name')))
    if len(all_names) != len(set(all_names)) or any(n in {'DIRECT', 'REJECT', 'GLOBAL'} for n in all_names):
        raise SafeError('Duplicate or reserved node/group name.')


def _append_sequence(text: str, seq: SequenceNode, additions: list, edits: list):
    if not isinstance(seq, SequenceNode):
        raise SafeError('Expected a YAML sequence.')
    if seq.flow_style or not seq.value:
        original = yaml.safe_load(text[seq.start_mark.index:seq.end_mark.index]) or []
        replacement = yaml.safe_dump(original + additions, default_flow_style=True,
                                     allow_unicode=True, width=100000).strip()
        edits.append((seq.start_mark.index, seq.end_mark.index, replacement))
        return
    # Insert after the last actual value line, before following comments/keys.
    last = seq.value[-1]
    end = last.end_mark.index
    if end and text[end - 1] == '\n':
        position = end
    else:
        newline = text.find('\n', end)
        position = newline + 1 if newline >= 0 else len(text)
    indent = seq.start_mark.column
    dumped = yaml.safe_dump(additions, allow_unicode=True, sort_keys=False,
                            default_flow_style=False, width=100000)
    prefix = '' if position == 0 or text[position - 1] == '\n' else '\n'
    inserted = prefix + ''.join(' ' * indent + line + '\n' for line in dumped.splitlines())
    edits.append((position, position, inserted))


def build_candidate(original: bytes, request: dict) -> tuple[bytes, dict]:
    value, tree, text = parse_yaml(original)
    _validated_profile(value)
    if not isinstance(request, dict) or set(request) - {'base_node', 'nodes', 'groups'}:
        raise SafeError('Unexpected node-manifest fields.')
    base = _name(request.get('base_node'))
    known = {n['name']: n for n in value['proxies']}
    if base not in known:
        raise SafeError('Base node was not found in this explicit profile.')
    incoming = request.get('nodes')
    if not isinstance(incoming, list) or not incoming:
        raise SafeError('Node manifest needs at least one verified node.')
    additions, names = [], []
    reserved = {g['name'] for g in value['proxy-groups']}
    for node in incoming:
        validate_node(node)
        name = node['name']
        if name in names or name in reserved or name in {'DIRECT', 'REJECT', 'GLOBAL'}:
            raise SafeError('Conflicting incoming node name.')
        names.append(name)
        if name in known and node != known[name]:
            raise SafeError('Existing node differs; refusing to overwrite credentials or settings.')
        if name not in known:
            additions.append(copy.deepcopy(node))
    group_names = request.get('groups')
    if group_names is None:
        group_names = [g['name'] for g in value['proxy-groups']
                       if g.get('type') == 'select' and base in g.get('proxies', [])]
    if not isinstance(group_names, list) or not group_names or len(set(group_names)) != len(group_names):
        raise SafeError('Specify unique selector groups that contain the base node.')
    edits = []
    _append_sequence(text, _field(tree, 'proxies'), additions, edits) if additions else None
    group_tree = _field(tree, 'proxy-groups')
    if not isinstance(group_tree, SequenceNode) or len(group_tree.value) != len(value['proxy-groups']):
        raise SafeError('Unsupported proxy-group layout.')
    expected = copy.deepcopy(value)
    expected['proxies'].extend(additions)
    found = []
    for group, node, target in zip(value['proxy-groups'], group_tree.value, expected['proxy-groups']):
        if group['name'] not in group_names:
            continue
        if group.get('type') != 'select' or base not in group.get('proxies', []):
            raise SafeError('Target group must be a selector containing the base node.')
        found.append(group['name'])
        extra = [name for name in names if name not in group['proxies']]
        target['proxies'].extend(extra)
        if extra:
            _append_sequence(text, _field(node, 'proxies'), extra, edits)
    if set(found) != set(group_names):
        raise SafeError('One or more requested groups do not exist.')
    ipv6_needed = any(':' in n['server'] for n in incoming)
    if ipv6_needed and value.get('ipv6') is not True:
        n = _field(tree, 'ipv6')
        if n is None:
            edits.append((0, 0, 'ipv6: true\n'))
        elif isinstance(n, ScalarNode):
            edits.append((n.start_mark.index, n.end_mark.index, 'true'))
        else:
            raise SafeError('Unsupported global ipv6 field.')
        expected['ipv6'] = True
    for start, end, replacement in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        text = text[:start] + replacement + text[end:]
    result, _, _ = parse_yaml(text)
    if result != expected:
        raise SafeError('Candidate failed semantic preservation checks; no changes made.')
    return text.encode(), {'added_nodes': [n['name'] for n in additions],
                           'groups': group_names, 'ipv6_enabled': ipv6_needed,
                           'rules_preserved': True, 'dns_preserved': True}


def inspect_profile(path: str) -> dict:
    value, _, _ = parse_yaml(read_bytes(path))
    _validated_profile(value)
    return {'profile_sha256': digest(read_bytes(path)), 'ipv6': value.get('ipv6', False),
            'nodes': [{'name': n['name'], 'type': n.get('type'), 'port': n.get('port'),
                       'address_family': 'ipv6' if ':' in str(n.get('server', '')) else 'ipv4-or-dns'}
                      for n in value['proxies']],
            'groups': [{'name': g['name'], 'type': g.get('type'), 'proxies': g.get('proxies', [])}
                       for g in value['proxy-groups']], 'rule_count': len(value.get('rules', []))}


def prepare(profile: str, nodes: str, state_dir: str) -> dict:
    source = explicit_path(profile, existing=True)
    before = read_bytes(source)
    request = read_json(nodes)
    after, summary = build_candidate(before, request)
    run = new_private_dir(state_dir)
    private_file(run / 'before.yaml', before)
    private_file(run / 'candidate.yaml', after)
    # The plan is private: it binds the reviewed exact profile and credentials.
    plan = {'schema': 'vps-clash-autopilot/plan-v1', 'source': str(source),
            'before_sha256': digest(before), 'after_sha256': digest(after),
            'request': request, 'summary': summary}
    private_json(run / 'plan.json', plan)
    return {'plan': str(run / 'plan.json'), **summary, 'source_modified': False}


def _plan(path: str):
    file = explicit_path(path, existing=True)
    run = file.parent
    if run.stat().st_mode & 0o077:
        raise SafeError('Plan directory must be private (0700).')
    plan = read_json(file)
    if plan.get('schema') != 'vps-clash-autopilot/plan-v1':
        raise SafeError('Unsupported plan schema.')
    before, candidate = read_bytes(run / 'before.yaml'), read_bytes(run / 'candidate.yaml')
    if digest(before) != plan['before_sha256'] or digest(candidate) != plan['after_sha256']:
        raise SafeError('Plan artifacts changed; prepare again.')
    recomputed, _ = build_candidate(before, plan['request'])
    if recomputed != candidate:
        raise SafeError('Candidate does not match the permitted incremental changes.')
    source = explicit_path(plan['source'], existing=True)
    if source.parent == run or source in {file, run / 'before.yaml', run / 'candidate.yaml'}:
        raise SafeError('Invalid source/plan overlap.')
    return source, plan, before, candidate


def apply(path: str, approved: bool, *, rollback: bool = False) -> dict:
    if not approved:
        raise SafeError('Explicit operator acknowledgment --approve is required after user authorization.')
    source, plan, before, after = _plan(path)
    current = digest(read_bytes(source))
    target, expected = (before, plan['after_sha256']) if rollback else (after, plan['before_sha256'])
    if current == digest(target):
        return {'changed': False, 'already_in_requested_state': True}
    atomic_replace(source, target, expected)
    if read_bytes(source) != target:
        raise SafeError('Readback mismatch; investigate before retrying.')
    return {'changed': True, 'rollback': rollback, 'readback_verified': True,
            'reload_required': True}
