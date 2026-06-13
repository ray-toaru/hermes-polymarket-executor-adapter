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

The deleted `v0.28-production-live-candidate` branch is historical and is not a
supported review anchor. New candidate or release claims must reference a full
commit SHA and an immutable annotated, signed tag.

This repository currently has one GitHub CODEOWNER. Until a second GitHub
collaborator is available, CODEOWNERS cannot enforce independent approval.
Credential, authorization, live-boundary, and release-governance changes must
therefore carry a separately verified external review reference; passing that
control does not grant live or production authorization.
