# Hermes Executor Adapter Roadmap

## Current Role

This repository is the Hermes executor adapter for the standalone Polymarket
execution engine. It owns typed executor API access, Pydantic public models,
safe report rendering, and service/admin token separation.

It does not own trading strategy, execution-engine risk policy, release/canary
governance, signing, direct CLOB access, or executor database credentials.

## v0.27 Development Status

- Package metadata and docs use `hermes-polymarket-executor-adapter`.
- Models and client helpers align with the executor OpenAPI contract through
  integration-repository parity checks.
- Canary readiness reporting remains reference-only and blocked unless a
  reviewed executor release decision and approval exist.
- Admin helpers call executor API endpoints only; they do not perform direct
  Polymarket operations.

## Remaining Before a v0.27 Suite Release

1. Keep model/client parity green against the execution-engine OpenAPI schema.
2. Keep no-secret and no-signing tests green under the integration repository.
3. Update supported executor contract notes if the execution-engine API changes
   before the v0.27 suite release.
