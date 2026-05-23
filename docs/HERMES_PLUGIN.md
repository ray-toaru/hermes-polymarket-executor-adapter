# Hermes Plugin Integration

## Purpose

The adapter exposes selected executor API calls as native Hermes tools through
the `polymarket-executor` plugin entry point. Hermes remains a caller of the
standalone executor API; it does not become the signer, CLOB gateway, executor
database writer, or risk-policy owner.

## Installation

Install this package into the same Python environment that runs Hermes:

```bash
python -m pip install -e .
hermes plugins enable polymarket-executor
```

Set runtime configuration:

```bash
export PM_EXEC_SERVICE_URL=http://localhost:8080
export PM_EXEC_SERVICE_TOKEN=...
export PM_EXEC_ADMIN_TOKEN=...  # admin tools only
```

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

Admin tools require both service and admin API tokens. Mutating admin tools also
require a human-readable `reason`.

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
hermes plugins list
hermes --list-tools
```

Confirm that `polymarket_executor` and `polymarket_executor_admin` appear only
after `polymarket-executor` is enabled.
