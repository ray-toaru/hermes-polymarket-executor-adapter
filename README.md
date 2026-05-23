# Hermes Polymarket Executor Adapter

Python Hermes-compatible executor adapter for the standalone Polymarket
execution engine.

## Boundary

This package may send typed service/admin/query requests to the executor API
and render safe reports for Hermes-compatible tooling. It must not hold private
keys, CLOB API secrets, raw signed payloads, or executor database credentials.
It must not sign, submit live orders, cancel live orders, call CLOB directly, or
own executor risk policy.

## v0.26 status

- Pydantic models aligned with OpenAPI public schemas.
- Canonical decimal validation aligned with executor source.
- Service/admin token client separation.
- Admin helpers for kill switch, cancel, and reconcile.
- Safe canary report helpers that do not authorize live trading.
- Tests pass in this environment.

## Run tests

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall -q src tests
```

Cross-repository OpenAPI parity is validated from the integration repository that checks out this
repo alongside `polymarket-execution-engine`.

## Agent instructions

See `AGENTS.md` for adapter-specific agent rules.
