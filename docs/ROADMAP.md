# Hermes Executor Adapter Roadmap

## Current Role

This repository is the Hermes executor adapter for the standalone Polymarket
execution engine. It owns typed executor API access, Pydantic public models,
safe report rendering, and service/admin token separation.

It does not own trading strategy, execution-engine risk policy, release/canary
governance, signing, direct CLOB access, or executor database credentials.

## Current v0.28 adapter status

- Package metadata and docs use `hermes-polymarket-executor-adapter`.
- Models and client helpers align with the executor OpenAPI contract through
  integration-repository parity checks.
- Canary readiness reporting remains reference-only and blocked unless a
  reviewed executor release decision and approval exist.
- Admin helpers call executor API endpoints only; they do not perform direct
  Polymarket operations.
- Hermes plugin entry point is present at `polymarket-executor`.
- Native Hermes service/admin toolsets are implemented with token gating.

## Stage Roadmap

### Stage 0: Boundary and Tool Inventory

Status: implemented.

- Service tools: health, normalize intent, capture snapshot, evaluate decision,
  compile plan, safe prepare execution plan, get submission, list lifecycle
  events, and canary report.
- Admin tools: kill switch, cancel order, reconcile, and list audit events.
- Forbidden surface remains excluded: signing, direct CLOB access, executor DB
  writes, reusable signed material, and release/canary governance ownership.

### Stage 1: Hermes Plugin Minimum Viable Integration

Status: implemented.

- `pyproject.toml` exposes the `hermes_agent.plugins` entry point and supports
  Python 3.11+ so it can run in current Hermes runtime profiles.
- `hermes_plugin.py` registers Hermes-native tools through `ctx.register_tool`.
- `hermes_handlers.py` adapts Hermes tool calls to `ExecutorClient`.
- `hermes_schemas.py` contains the tool schemas shown to Hermes.

### Stage 2: Permission Isolation and Safety Tests

Status: implemented for local adapter tests; integration-repository checks still
remain part of suite release validation.

- Service tools require `PM_EXEC_SERVICE_TOKEN`.
- Admin tools require both `PM_EXEC_SERVICE_TOKEN` and `PM_EXEC_ADMIN_TOKEN`.
- Admin handlers require explicit reasons where the executor admin API mutates
  state.
- No-secret/no-signing tests include newly added Python source files.

### Stage 3: OpenAPI Contract Alignment

Status: implemented for the current handwritten adapter contract.

- Pydantic models and client helpers are currently handwritten.
- Cross-repository parity checks remain the authority when executor public
  schemas change.
- Future improvement: generate or mechanically derive client/schema code from
  OpenAPI once the executor API stabilizes further.

### Stage 4: Safe Execution Workflow Wrapper

Status: implemented.

- Hermes can invoke each standard executor step explicitly.
- `polymarket_prepare_execution_plan` chains normalize, snapshot, decision, and
  compile after explicit approval.
- The wrapper does not submit plans.

### Stage 5: Admin Tooling and Auditability

Status: implemented for admin API wrappers.

- Admin tools are in a separate toolset.
- Admin calls require admin token availability.
- Cancellation and reconciliation accept correlation ids for traceability.
- Audit events can be queried separately.

### Stage 6: Operator Documentation

Status: implemented.

- `README.md` documents install and runtime token setup.
- `docs/HERMES_PLUGIN.md` documents tool names, enablement, and boundaries.
- `docs/SECURITY_BOUNDARIES.md` remains the security boundary source.

### Stage 7: MCP Facade Evaluation

Status: evaluated, not implemented.

- The native Hermes plugin remains the primary integration path.
- MCP is suitable only when the same adapter tools need to be reused by
  non-Hermes agents or deployed as an isolated external tool server.
- Any MCP implementation must reuse the same client/models and must not add
  signing, direct CLOB, executor DB write, or secret-bearing behavior.
- See `docs/MCP_EVALUATION.md`.

## Current v0.28 release prerequisites

1. Keep model/client parity green against the execution-engine OpenAPI schema.
2. Keep no-secret and no-signing tests green under the integration repository.
3. Update supported executor contract notes if the execution-engine API changes
   before the v0.28 suite release.
4. Validate the plugin inside the target Hermes profile from the integration
   repository root, or invoke the adapter wrapper with `python
   scripts/check_hermes_profile_plugin.py --suite-root
   /path/to/polymarket-execution-suite --profile-cmd
   <local-profile-command>`.
