"""Explicit public-source inventory and privacy guard. No runtime directories read."""
from __future__ import annotations
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'.git', '.venv', 'reports', 'dist', '__pycache__', '.pytest_cache'}

def scan_text(text: str) -> list[str]:
    findings = []
    patterns = {
        'private-key material': r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----',
        'personal filesystem path': r'/(?:Users|home)/[A-Za-z0-9_-]+/',
        'email address': r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        'access token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{25,})\b',
    }
    for label, pattern in patterns.items():
        if re.search(pattern, text, re.I):
            findings.append(label)
    allowed = [ipaddress.ip_network(s) for s in ('192.0.2.0/24', '198.51.100.0/24', '203.0.113.0/24', '127.0.0.0/8')]
    for match in re.findall(r'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])', text):
        try:
            address = ipaddress.ip_address(match)
        except ValueError:
            continue
        if str(address) != '0.0.0.0' and not any(address in net for net in allowed):
            findings.append('non-documentation IPv4 address')
    # Actual IPv6 literals: allow documentation/loopback only, excluding generic regex/code fragments.
    for candidate in re.findall(r'(?<![\w:])[0-9a-fA-F]*:[0-9a-fA-F:]+(?![\w:])', text):
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.version == 6 and address not in ipaddress.ip_network('2001:db8::/32') and address != ipaddress.ip_address('::1'):
            findings.append('non-documentation IPv6 address')
    return sorted(set(findings))

def check(root: Path = ROOT) -> list[dict]:
    names = json.loads((root / 'public-files.json').read_text())['files']
    if len(names) != len(set(names)):
        raise ValueError('Duplicate public entry')
    listed = set(names)
    observed = set()
    def walk(folder):
        for p in folder.iterdir():
            rel = p.relative_to(root).as_posix()
            if p.name in EXCLUDED:
                continue
            if p.name.startswith('.env'):
                raise ValueError('Environment files must remain outside the public package')
            if p.is_symlink():
                if rel != 'CLAUDE.md' or p.readlink().as_posix() != 'AGENTS.md':
                    raise ValueError('Unreviewed symlink')
                observed.add(rel)
            elif p.is_dir():
                walk(p)
            else:
                observed.add(rel)
    walk(root)
    if observed != listed:
        raise ValueError('Public inventory mismatch: missing or unreviewed files')
    results = []
    for name in names:
        if Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Unsafe public path')
        path = root / name
        raw = path.read_bytes()
        issues = scan_text(raw.decode('utf-8'))
        if issues:
            raise ValueError(name + ': ' + ', '.join(issues))
        results.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    return results

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', help='New ZIP path, inside the local dist folder')
    args = parser.parse_args()
    try:
        files = check()
        if args.archive:
            dest = Path(args.archive).absolute()
            if dest.parent != ROOT / 'dist' or dest.exists():
                raise ValueError('Archive must be a new file directly under dist/')
            dest.parent.mkdir(exist_ok=True)
            with zipfile.ZipFile(dest, 'x', compression=zipfile.ZIP_DEFLATED) as bundle:
                for entry in files:
                    # Materialize the reviewed CLAUDE link as its identical rule text for portable ZIPs.
                    bundle.writestr('vps-clash-autopilot/' + entry['path'], (ROOT / entry['path']).read_bytes())
            with zipfile.ZipFile(dest) as bundle:
                if bundle.testzip() is not None or len(bundle.namelist()) != len(files):
                    raise ValueError('Archive verification failed')
        print(json.dumps({'status': 'pass', 'files': files, 'limits': 'Heuristic scan plus human review; not proof that every possible secret is detected.'}, indent=2))
    except (ValueError, OSError, UnicodeError, KeyError):
        # Never echo matched secret values.
        parser.exit(1, 'Release inventory/privacy check failed. Review the explicit source allowlist locally.\n')

if __name__ == '__main__':
    main()
