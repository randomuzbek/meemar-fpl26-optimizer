# Security policy

## Scope

This repository contains a frozen contest submission, two analysis tools, hardware benchmark
sources and documentation. It is not a service, it stores no user data, and it has no network
listener.

Two things here are nonetheless worth reporting:

- **A credential, key, token or other secret found anywhere in the repository or its history.**
  The repository was built from a scrubbed extraction precisely to prevent this, and
  `scripts/scrub_check.sh` guards it in CI, but a miss is possible and is the highest-severity
  issue this project can have.
- **A vulnerability in `tools/pack.py` or `tools/harness_timeline.py`** — for example path
  traversal when extracting a harness log archive, or unsafe handling of an attacker-supplied
  zip.

Out of scope: the behaviour of the optimizer itself, Vivado, RapidWright, the MCP servers, and
anything under `submission/`, which cannot be changed (see [CONTRIBUTING.md](CONTRIBUTING.md)).

## Reporting

Please report privately, not in a public issue.

Use GitHub's **Report a vulnerability** button under the Security tab of this repository, which
opens a private advisory. If that is unavailable, email the address in
[CITATION.cff](CITATION.cff).

Expect an acknowledgement within seven days. This is a personal project maintained by one person,
so please size your expectations accordingly — but a reported secret will be handled immediately.

## Supported versions

The current release is supported. Older tags are historical records of the submission and will not
receive fixes.
