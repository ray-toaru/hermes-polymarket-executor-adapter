# Contributing

Target `main` with a focused pull request. Run the Python tests, Ruff, mypy,
Bandit, and wheel smoke checks described in `AGENTS.md` or CI.

The adapter must remain a non-signing, non-CLOB, non-database boundary. Never
add private keys, CLOB credentials, raw signatures, signed payloads, or
approval-granting behavior.

Use squash merge. Credential and authorization-boundary changes require an
independent external review reference until a second repository reviewer is
available.

Release tags must be annotated and cryptographically signed. Existing unsigned
tags remain immutable historical records.
