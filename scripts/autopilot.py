#!/usr/bin/env python3
"""Local helpers for a host Agent. Run --help; no operation discovers credentials."""
from __future__ import annotations

import argparse
import json
import sys

from common import SafeError
from profile_ops import apply, inspect_profile, prepare
from runtime_ops import export_mobile, switch_groups, verify


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    s = commands.add_parser('inspect', help='Read only: summarize an explicit profile without credentials.')
    s.add_argument('--profile', required=True)
    s = commands.add_parser('prepare', help='Create a private backup, candidate and hash-bound plan; source unchanged.')
    s.add_argument('--profile', required=True)
    s.add_argument('--nodes', required=True, help='Private verified-node JSON; never a .env file.')
    s.add_argument('--state-dir', required=True, help='New private directory outside the public repository.')
    for command in ['apply', 'rollback']:
        s = commands.add_parser(command, help='Apply reviewed plan or restore only if hashes still match.')
        s.add_argument('--plan', required=True)
        s.add_argument('--approve', action='store_true', help='Operator acknowledgment; does not replace actual user consent.')
    s = commands.add_parser('switch', help='Switch explicit selectors with best-effort recovery and readback.')
    s.add_argument('--socket', required=True)
    s.add_argument('--node', required=True)
    s.add_argument('--groups', nargs='+', required=True)
    s.add_argument('--approve', action='store_true')
    s = commands.add_parser('verify', help='Bounded probes; never reports TUN/browser acceptance from HTTP alone.')
    s.add_argument('--proxy', help='Explicit HTTP loopback proxy; omit for --noproxy * system-path probes.')
    s.add_argument('--repeats', type=int, default=3)
    s.add_argument('--output', help='New private report file inside a 0700 directory.')
    s = commands.add_parser('mobile', help='Export private offline QR page and node links, with certificate pins.')
    s.add_argument('--profile', required=True)
    s.add_argument('--output-dir', required=True)
    s.add_argument('--names', nargs='+')
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        if a.command == 'inspect':
            result = inspect_profile(a.profile)
        elif a.command == 'prepare':
            result = prepare(a.profile, a.nodes, a.state_dir)
        elif a.command in {'apply', 'rollback'}:
            result = apply(a.plan, a.approve, rollback=a.command == 'rollback')
        elif a.command == 'switch':
            result = switch_groups(a.socket, a.node, a.groups, a.approve)
        elif a.command == 'verify':
            result = verify(a.proxy, a.repeats, a.output)
        else:
            result = export_mobile(a.profile, a.output_dir, a.names)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False, indent=2))
        return 0
    except SafeError as e:
        print(json.dumps({'ok': False, 'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception:
        # Third-party parse, HTTP and filesystem exceptions can contain secrets.
        print(json.dumps({'ok': False, 'error': 'Operation stopped; input/response details withheld. Inspect target state before retrying.'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
