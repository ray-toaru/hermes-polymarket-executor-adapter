# Hermes Polymarket Executor Adapter

Python Hermes-compatible executor adapter for the standalone Polymarket
execution engine.

## Boundary

This package may send typed service/admin/query requests to the executor API
and render safe reports for Hermes-compatible tooling. It must not hold private
keys, CLOB API secrets, raw signed payloads, or executor database credentials.
It must not sign, submit live orders, cancel live orders, call CLOB directly, or
own executor risk policy.

## v0.27 development status

- Pydantic models aligned with OpenAPI public schemas.
- Canonical decimal validation aligned with executor source.
- Service/admin token client separation.
- Admin helpers for kill switch, cancel, and reconcile.
- Safe canary report helpers that do not authorize live trading.
- Hermes plugin entry point exposes a native `polymarket_executor` toolset and
  a separate `polymarket_executor_admin` toolset.
- Assistant-v0 safe session contract keeps local assistant tools separate from
  adapter-backed executor tools and rejects signing, posting, cancel-live, raw
  CLOB, direct DB, and approval-granting tool names.
- Hermes executor adapter naming and package metadata are aligned with the
  repository responsibility boundary.
- Boundary remains no signing, no direct CLOB, no executor database credentials,
  and no release/canary governance ownership.
- Tests pass in this environment.

## Hermes plugin

Install the adapter into the Hermes Python environment and enable the plugin:

```bash
python -m pip install -e .
hermes plugins enable polymarket-executor
```

Configure executor API tokens at runtime:

```bash
export PM_EXEC_SERVICE_URL=http://localhost:8080
export PM_EXEC_SERVICE_TOKEN=...
export PM_EXEC_ADMIN_TOKEN=...  # only required for admin tools
```

Service tools are registered under `polymarket_executor`; admin tools are
registered under `polymarket_executor_admin` and require both service and admin
tokens. See `docs/HERMES_PLUGIN.md` for the tool list and operating boundary.
The composite `polymarket_prepare_execution_plan` tool stops at plan
compilation and does not submit.

## Run tests

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall -q src tests
```

Cross-repository OpenAPI parity is validated from the integration repository that checks out this
repo alongside `polymarket-execution-engine`.

## Integration roadmap

Stages 0-7 are tracked in `docs/ROADMAP.md`. MCP is intentionally a phase-7
facade evaluation after the native Hermes plugin path is stable; it must reuse
the same no-signing adapter boundary if implemented.

## Agent instructions

See `AGENTS.md` for adapter-specific agent rules.
