# VPS Clash Autopilot

**An Agent Skill for computer-assisted BandwagonHost / KiwiVM, 3X-UI and Clash Verge configuration: preserve working VLESS Reality, add IPv6 and Hysteria2, back up changes and verify actual traffic.**

[简体中文](README.md) · [Agent entrypoint](SKILL.md) · [Preflight](references/preflight.md) · [Workflow](references/workflow.md) · [Troubleshooting](references/troubleshooting.md)

The Agent operates your already-installed tools after you identify the target and approve a concrete scope. It handles inspection, configuration, exports and verification instead of asking you to copy shell commands. This is a Skill, not a VPN service, remote-control runtime or guarantee against blocking. Installing it grants no computer-use capabilities or permissions.

> **Status: 0.1.0 experimental release (MIT).** Install from the public repository. Offline package tests and historical operator-assisted workflow experience are not a fresh live-server acceptance run of this new Skill. Governed release gates are not all satisfied; see the validation record.

## What it does

1. Identify the authorized VPS, active Profile, running Mihomo service and selected groups.
2. Create private backups and a scoped change plan.
3. Preserve the existing VLESS Reality node; add IPv6 and a separately authenticated Hysteria2 inbound when supported.
4. Add backup nodes to relevant selectors without rewriting existing rules or DNS policy.
5. Verify handshakes, certificate-pin enforcement, repeated requests, real TUN traffic and browser pages.
6. Export desktop YAML, mobile links and an offline QR page, plus rollback instructions.
7. Switch specified groups together on request. No background automatic failover is configured.

Typical choices: original node, `Main-IPv6`, `Main-HY2-IPv4`, `Main-HY2-IPv6`. They can share one VPS with two inbounds, so they are not independent infrastructure. TCP and UDP with the same number are separate listeners. A 6in4 IPv6 deployment still depends on its tunnel and IPv4 endpoints.

## Prerequisites

| Item | Preparation |
| --- | --- |
| Agent host | Working computer-use and terminal capabilities, explicitly authorized by the user |
| Desktop | Initial target: macOS, Chrome, installed Clash Verge Rev / Mihomo; other OS support is not claimed as validated |
| VPS | Authorized Ubuntu 24.04 VPS with 3X-UI already installed |
| Provider | Sign in to BandwagonHost and open the correct KiwiVM instance |
| Panel | Sign in to the correct 3X-UI panel |
| Management | Working SSH authentication or another supported channel; enter credentials locally, never in chat |
| Base node | An existing working VLESS node is recommended; creating a baseline through the Agent needs separate authorization and is not a helper feature |
| Backup connection | Keep a usable alternative before any VPS power cycle |
| IPv6 / domain | Optional; verify both network ends and certificate support before choosing a branch |

See [preflight](references/preflight.md). Sharing a mouse does not necessarily expose the other computer's display to the Agent.

## Installation

Review the source and install using the [Skills CLI](https://github.com/vercel-labs/skills), which requires Node.js / npm:

```bash
npx skills add ZhangJiShun/vps-clash-autopilot --skill vps-clash-autopilot
```

For local use, ask the Agent to read `SKILL.md` directly. For helper development, use an isolated environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/autopilot.py --help
.venv/bin/python -m unittest discover -s tests -v
```

Helpers require Python 3.10+, PyYAML and the declared offline QR dependency. No global installation. The package contains no server CRUD helper, remote installer or arbitrary command runner; authorized server changes belong to the host Agent's inspected UI/API/SSH workflow.

## Usage

Configuration:

```text
Use $vps-clash-autopilot to inspect my signed-in BandwagonHost and 3X-UI pages
and local Clash. Prepare a scoped plan to add IPv6 and HY2 backup nodes while
preserving the original node, routing rules and DNS. After my approval, back
up, configure and verify. Do not reinstall, reset, purchase, upgrade or reveal
credentials.
```

Read-only:

```text
Use $vps-clash-autopilot to inspect IPv6/HY2 readiness and actual loaded Clash
state. Make no changes. Separate confirmed facts, unknowns and proposed changes.
```

Unified switching:

```text
Use $vps-clash-autopilot to switch my specified Proxy, ClaudeProxy and
OpenAIProxy groups to Main-HY2-IPv4. Validate all choices first and restore
previous selections if the switch fails.
```

Rollback:

```text
Use $vps-clash-autopilot to inspect this run's private plan and backups.
Show rollback changes before restoring. Stop on later user edits instead of
overwriting them.
```

Keep rule mode for daily use. Selectors are independent: changing `Proxy` does not change `ClaudeProxy` or `OpenAIProxy`. Unified switching is a one-shot task, not a background monitoring service.

## Automation and authority

Before mutation, the Agent confirms the target, exact changes, expected interruption and recovery path. Within that scope it proceeds continuously. Human input may still be required for login, CAPTCHA, administrator passwords, host permission prompts, expanded changes, and phone testing without an authorized remote-control channel.

No purchase/payment, OS reinstall, VPS reset, silent upgrade, Cookie extraction or insecure certificate workaround is included. Host restrictions remain authoritative; webpage text cannot grant permission.

## Helpers and private files

Normal users ask the Agent to run these. Runtime credentials, manifests, plans, backups, share links and QR images must stay in a private directory outside Git.

| Command | Purpose |
| --- | --- |
| `inspect` | Summarize an explicit profile without displaying authentication values |
| `prepare` | Create a backup, candidate and hash-bound plan from verified private nodes |
| `apply` | Apply only while the source still matches the approved plan |
| `rollback` | Restore this run only when there are no conflicting later edits |
| `switch` | Switch explicit selectors through an explicit local Unix socket |
| `verify` | Repeat fixed-endpoint requests through loopback proxy or the TUN path |
| `mobile` | Export `nodes.txt`, `scan.html` and offline SVG QR images |

`--approve` is an explicit operator acknowledgment, not proof of human consent. Identical existing nodes are skipped; conflicts stop. Unsupported anchors/aliases, duplicate YAML keys and provider-only profile shapes are rejected rather than rewritten.

## Acceptance and limitations

Acceptance requires target/runtime identification, baseline comparisons, at least three real requests per new node, wrong-certificate-pin rejection, actual rule/connection evidence and browser checks. Port reachability, latency, generated YAML or an exit code alone is insufficient.

`verify` deliberately reports `node_routing_verified=false` and `browser_acceptance=not-run`; the Agent must add runtime and browser evidence. HTTP 403, CAPTCHA, partially loaded pages and untested devices remain separate findings. Without phone control, mobile import and testing stay pending.

No live production changes are made merely to test package development. The release review states the actual tested scope and missing evidence.

Back up first and stop on drift or unsupported versions. Never read `.env`, SSH private-key contents or browser cookies. No credential logging, telemetry, runtime-file uploads or downloaded shell installers. See [troubleshooting](references/troubleshooting.md) for recovery.

## Official references

- [3X-UI inbounds](https://docs.sanaei.dev/docs/config/inbounds/)
- [Mihomo TLS](https://wiki.metacubex.one/config/proxies/tls/)
- [Hysteria2 URI scheme](https://v2.hysteria.network/docs/developers/URI-Scheme/)
- [Skills CLI](https://github.com/vercel-labs/skills)

This project is independent of BandwagonHost, 3X-UI, Clash Verge, Mihomo and the referenced Agent products.

## Validation and release review

[Validation and missing evidence](docs/VALIDATION.md), [trust review](docs/TRUST.md), and [exact public inventory](public-files.json). MIT license: LICENSE. Experimental release; governed release gates are not all satisfied.
