# Hermes Executor Adapter Progress

## Done

- Basic package structure under `hermes_polymarket_executor_adapter`.
- Pydantic models aligned to executor public schemas.
- Typed executor client for service, admin, and query paths.
- Client, model, CLI, and no-secret boundary tests.
- Safe canary readiness report rendering that remains blocked by default.
- Hermes plugin entry point for `polymarket-executor`.
- Native Hermes service toolset wrappers for executor service/query paths.
- Native Hermes admin toolset wrappers with explicit admin token gating.
- Local plugin registration, availability, handler, and canary boundary tests.
- Documentation of forbidden responsibilities: no signing, no direct CLOB, no
  executor database credentials, no release/canary governance ownership.
- Operator documentation for Hermes plugin setup and MCP evaluation.
- Local `hm-pdp-test` Hermes runtime validation: the entry-point plugin is
  importable in the Hermes runtime venv and exposes `polymarket_executor` plus
  `polymarket_executor_admin` toolsets.

## Still Required Before v0.27 Suite Release

- Re-run adapter tests from the integration repository after any executor API
  schema change.
- Keep package/version compatibility recorded in `COMPONENT_COMPATIBILITY.md`.
- Preserve the adapter as a Hermes executor adapter only; execution authority
  remains in `polymarket-execution-engine`.
- Replace the current local profile install procedure with a packaged Hermes
  plugin distribution if Hermes keeps directory plugins and pip entry-point
  plugin enablement on separate CLI paths.
