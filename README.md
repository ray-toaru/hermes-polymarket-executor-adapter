# Hermes Polymarket Executor Adapter

Python Hermes-compatible executor adapter for the standalone Polymarket
execution engine.

## Boundary

This package may send typed service/admin/query requests to the executor API
and render safe reports for Hermes-compatible tooling. It must not hold private
keys, CLOB API secrets, raw signed payloads, or executor database credentials.
It must not sign, submit live orders, cancel live orders, call CLOB directly, or
own executor risk policy.

## Current v0.28 adapter status

- Pydantic models aligned with OpenAPI public schemas.
- Canonical decimal validation aligned with executor source.
- Service/admin token client separation.
- Admin helpers for kill switch, cancel, reconcile, audit-event queries, and
  live-read event queries.
- Safe canary report helpers that do not authorize live trading.
- Hermes plugin entry point exposes a native `polymarket_executor` toolset and
  a separate `polymarket_executor_admin` toolset.
- Assistant-v0 safe session contract keeps local assistant tools separate from
  adapter-backed executor tools and rejects signing, posting, cancel-live, raw
  CLOB, direct DB, and approval-granting tool names.
- The optional `polymarket_assistant_v0` facade registers only risk review,
  blocked dry-run, and status tools. Its default handlers do not call the
  executor and always keep live submission false until explicit executor-backed
  implementations replace the stubs.
- Hermes executor adapter naming and package metadata are aligned with the
  repository responsibility boundary.
- Boundary remains no signing, no direct CLOB, no executor database credentials,
  and no release/canary governance ownership.
- CI and local validation should run the checks listed below before publishing
  adapter changes.

## Hermes plugin

Install the adapter into the Hermes Python environment:

```bash
python -m pip install -c constraints-ci.txt -e .
```

Then add `polymarket-executor` to the active Hermes profile's
`plugins.enabled` allow-list. `hermes plugins enable` only manages
directory-managed plugins and is not the correct activation path for this
entry-point plugin.

Configure executor API tokens at runtime:

```bash
export PM_EXEC_SERVICE_URL=http://executor-host:8080
export PM_EXEC_SERVICE_TOKEN=...
export PM_EXEC_ADMIN_TOKEN=...  # only required for admin tools
```

`PM_EXEC_SERVICE_URL` is required. The adapter will not silently default to a
local executor host.
These are adapter client credentials: set `PM_EXEC_SERVICE_TOKEN` to the target
engine API's `PMX_API_SERVICE_TOKEN` value, and set `PM_EXEC_ADMIN_TOKEN` to the
target engine API's `PMX_API_ADMIN_TOKEN` value.

Service tools are registered under `polymarket_executor`; admin tools are
registered under `polymarket_executor_admin` and require both service and admin
tokens. See `docs/HERMES_PLUGIN.md` for the tool list and operating boundary.
The composite `polymarket_prepare_execution_plan` tool stops at plan
compilation and does not submit. The low-level `submit_plan` client method is
retained only for explicit executor-side `BLOCKED_DRY_RUN` submission; the
adapter does not permit live submit mode.

## Run tests

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/check_openapi_parity.py /path/to/polymarket-execution-engine/openapi/executor.v1.yaml
python -m ruff check src tests
python -m mypy src
python -m bandit -q -r src
PYTHONPATH=src python -m compileall -q src tests
python -m build --sdist --wheel
pmx-executor-adapter --help
```

Adapter CI checks out a pinned execution-engine commit and validates Pydantic
field, required-field, and `additionalProperties` parity against
`executor.v1.yaml`. The integration repository repeats the check against the
submodule commits selected for a suite release.
Adapter-local contract compatibility is tracked in
`docs/COMPONENT_COMPATIBILITY.md`.

## Integration roadmap

Stages 0-7 are tracked in `docs/ROADMAP.md`. MCP is intentionally a phase-7
facade evaluation after the native Hermes plugin path is stable; it must reuse
the same no-signing adapter boundary if implemented.

## Agent instructions

See `AGENTS.md` for adapter-specific agent rules.
