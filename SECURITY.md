# Security Policy

## Supported Versions

Security fixes are accepted for the current `main` branch and any explicitly
published release-candidate commit that remains reproducible by immutable tag or
commit SHA. Historical archive material and deleted candidate refs are not
supported versions.

## Reporting

Report vulnerabilities privately through GitHub security reporting or a private
channel to the repository owner. Do not place tokens, private keys, account
identifiers, raw signatures, signed payloads, or CLOB secrets in public issues,
pull requests, logs, or attachments.

Use synthetic data and include:

- affected commit SHA or immutable tag;
- affected package version;
- impact and reachable boundary;
- reproduction steps using redacted fixtures;
- whether signing, live submit, live cancel, CLOB access, or secret exposure is
  implicated;
- containment recommendation.

## Response Targets

Initial triage target: 3 business days after private receipt.
Containment target for confirmed high-impact issues: 7 business days when a
local code or documentation fix is sufficient. External dependency,
infrastructure, or reviewer-availability blockers must be recorded explicitly.

## Disclosure

Public disclosure should wait until a fix, mitigation, or explicit non-affected
analysis is available. Security fixes must preserve the adapter boundary: no
private keys, no raw signatures, no signed order envelopes, no direct CLOB
calls, no executor database credentials, no live submit, and no live cancel.
