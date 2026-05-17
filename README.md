# Hermes Polymarket Control

Python control-plane client for the standalone Polymarket execution engine.

## Boundary

This package may submit intents and admin commands to the executor API. It must not hold private keys, CLOB API secrets, raw signed payloads, or executor database credentials.

## v0.3 status

- Pydantic models aligned with OpenAPI public schemas.
- Canonical decimal validation aligned with executor source.
- Service/admin token client separation.
- Admin helpers for kill switch, cancel, and reconcile.
- Tests pass in this environment.

## Run tests

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall -q src tests
```

Cross-repository OpenAPI parity is validated from the integration repository that checks out this
repo alongside `polymarket-execution-engine`.

## Agent instructions

See `AGENTS.md` for control-plane-specific agent rules.
