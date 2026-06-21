# Hermes Plugin Integration

## Purpose

The adapter exposes selected executor API calls as native Hermes tools through
the `polymarket-executor` plugin entry point. Hermes remains a caller of the
standalone executor API; it does not become the signer, CLOB gateway, executor
database writer, or risk-policy owner.

## Installation

Install this package into the same Python environment that runs Hermes:

```bash
uv pip install --python "$HERMES_RUNTIME_PYTHON" -e .
```

For reproducible local development outside the Hermes runtime, prefer:

```bash
python -m pip install -c constraints-ci.txt -e ".[test]"
```

The current Hermes CLI discovers pip entry-point plugins at runtime, but
`hermes plugins enable` only enables directory-managed plugins. For a local
profile, enable this entry-point plugin by adding `polymarket-executor` to the
profile's `plugins.enabled` allow-list. From an adapter checkout, delegate the
profile check to an explicit integration repository:

```bash
python scripts/check_hermes_profile_plugin.py --suite-root /path/to/polymarket-execution-suite --profile-cmd "$HERMES_PROFILE_CMD"
"$HERMES_PROFILE_CMD" tools list --platform cli
```

From the integration repository itself, run its script directly:

```bash
cd /path/to/polymarket-execution-suite
python scripts/check_hermes_profile_plugin.py --profile-cmd "$HERMES_PROFILE_CMD"
```

Set runtime configuration:

```bash
export PM_EXEC_SERVICE_URL=http://localhost:8080
export PM_EXEC_SERVICE_TOKEN=...
export PM_EXEC_ADMIN_TOKEN=...  # admin tools only
```

`PM_EXEC_SERVICE_URL` is required. The adapter does not silently default to a
local executor URL.
These are adapter client credentials: set `PM_EXEC_SERVICE_TOKEN` to the target
engine API's `PMX_API_SERVICE_TOKEN` value, and set `PM_EXEC_ADMIN_TOKEN` to the
target engine API's `PMX_API_ADMIN_TOKEN` value.

## Toolsets

Service/query tools use the `polymarket_executor` toolset:

- `polymarket_executor_health`
- `polymarket_normalize_intent`
- `polymarket_capture_snapshot`
- `polymarket_evaluate_decision`
- `polymarket_compile_plan`
- `polymarket_prepare_execution_plan`
- `polymarket_get_submission`
- `polymarket_list_execution_lifecycle_events`
- `polymarket_canary_report`

Admin tools use the `polymarket_executor_admin` toolset:

- `polymarket_admin_kill_switch`
- `polymarket_admin_cancel_order`
- `polymarket_admin_reconcile`
- `polymarket_admin_list_audit_events`
- `polymarket_admin_list_live_read_events`

Admin tools require both service and admin API tokens. Mutating admin tools also
require a human-readable `reason`.

## Assistant-v0 safe session contract

`hermes_polymarket_executor_adapter.assistant_v0_contracts` defines the
optional assistant-facing safe-session contract. It is intentionally narrower
than the executor API:

- adapter-backed required tools: `risk_review_trade_plan`,
  `dry_run_trade_plan`, `get_execution_status`
- assistant-local tools may draft, compare, record review references, and
  render reports without gaining executor-side authority
- `dry_run_trade_plan` always maps to `BLOCKED_DRY_RUN`; callers cannot pass a
  live mode or an `approval_id` alias
- forbidden names include signing, posting, live cancel, raw CLOB, direct DB,
  fund transfer, API-key creation, and approval-granting tools

This contract is a local schema/guard for assistant sessions. It does not
authorize live trading and does not replace executor release decisions,
runtime truth, or canary approval checks.

The plugin also exposes the required assistant-v0 adapter tools under
`polymarket_assistant_v0`. The current facade is deliberately fail-closed:
`risk_review_trade_plan`, `dry_run_trade_plan`, and `get_execution_status`
return structured non-live responses without submitting, signing, canceling, or
granting approval. This keeps the assistant surface testable while preserving
the executor API as the only authority for real execution.

## Boundary

The plugin must not:

- sign orders
- hold private keys
- hold Polymarket CLOB credentials
- call Polymarket CLOB directly
- write executor database state directly
- construct reusable signed material
- authorize live trading from a local canary report

Every remote operation goes through the executor API via `ExecutorClient`.

## Validation

From this repository:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall -q src tests
```

Hermes runtime validation before suite release:

```bash
python scripts/check_hermes_profile_plugin.py --suite-root /path/to/polymarket-execution-suite --profile-cmd "$HERMES_PROFILE_CMD"
"$HERMES_PROFILE_CMD" tools list --platform cli
```

Confirm that `polymarket_executor` and `polymarket_executor_admin` appear only
after `polymarket-executor` is installed in the Hermes runtime environment and
enabled in the active profile.
