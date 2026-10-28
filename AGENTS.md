# vps-clash-autopilot

This repository ships an Agent Skill and local Python helpers. Do not operate a real VPS, router, browser account or installed Clash during development or tests.

- Python 3.10+, PyYAML; test with `python3 -m unittest discover -s tests -v`.
- Runtime credentials and artifacts live outside this repository. Never read `.env` files, SSH private keys or browser cookies. Use only synthetic documentation addresses in fixtures.
- Local changes must preserve existing nodes, routing/DNS configuration, and comments where practical. Plan/apply/rollback use content hashes and collision checks; never silently overwrite user work.
- Only documented Unix-socket API paths are permitted; no TCP controller exposure, arbitrary shell execution, telemetry, or remote installers in helpers.
- Changes to a real server require the calling Agent's target-scoped user authorization. A local approval flag is an explicit operator acknowledgment, never proof of human consent.
- Public readiness claims must distinguish fixture tests, historical workflow evidence and an actual run of this package. Do not invent reviews or end-to-end acceptance.
- Publishing requires the user's final review of the exact public file list. Do not create a remote, push, or publish releases during draft preparation.
- Keep generated Yao reports/build output out of the public source allowlist. Human-facing docs are README.md and README.en.md; SKILL.md is the Agent entrypoint.
