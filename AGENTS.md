# AGENTS.md — Hermes control plane

## Scope

Applies to this repository, the Python control-plane client.

## Boundary

- This package submits intents and admin/query requests to the executor API.
- It must not hold private keys, CLOB API secrets, raw signed payloads, signed order envelopes, or executor database credentials.
- It must not sign orders, submit live orders, cancel live orders, or call Polymarket CLOB directly.

## Development rules

- Keep Pydantic models aligned with the execution-engine OpenAPI contract.
- When API schemas change, update models, client helpers, and tests together.
- Preserve service/admin token separation.
- Keep decimal, enum, and lifecycle validation behavior consistent with executor public schemas.
- Do not add runtime dependencies without updating `pyproject.toml` and documenting why the dependency is needed.

## Validation

From this directory:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m compileall -q src tests
```

From the integration repository root, when this repository is checked out as `hermes-polymarket-control`:

```bash
PYTHONPATH=hermes-polymarket-control/src python -m pytest -q hermes-polymarket-control/tests
python -m compileall -q hermes-polymarket-control/src hermes-polymarket-control/tests
```

## Documentation

- Keep `README.md` and `docs/SECURITY_BOUNDARIES.md` aligned with the no-signing/no-secret boundary.
- Do not duplicate long architecture text here; link or update the integration and executor docs instead.
