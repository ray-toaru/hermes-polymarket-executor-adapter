# Hermes Executor Adapter Component Compatibility

## Scope

This file records the adapter-local compatibility surface. It is not a suite
release decision and it does not override the integration repository's pinned
submodule commits or release evidence.

## Supported Contract Surfaces

| Surface | Supported value | Notes |
| --- | --- | --- |
| Executor HTTP contract | `executor.v1` | Public executor API contract exposed by `polymarket-execution-engine/openapi/executor.v1.yaml`. |
| Assistant contract | `assistant-v0` | Safe-session assistant facade contract enforced by `assistant_v0_contracts.py` and the manifest loader. |
| Hermes plugin entry point | `polymarket-executor` | Python package entry point under `hermes_agent.plugins`. |
| Python runtime | `>=3.11` | CI currently exercises 3.11, 3.12, 3.13, and 3.14. |

## Compatibility Rules

- This adapter may version independently from the execution engine, but any
  suite release must pin an adapter commit and an execution-engine commit that
  were validated together.
- The adapter only claims support for the executor public HTTP contract named
  above. Private executor internals, database schemas, and signer/runtime
  implementation details are not part of the adapter compatibility contract.
- When the executor HTTP contract changes, update:
  - Pydantic models
  - schema wrappers
  - client helpers
  - compatibility claims in this file
  - tests that validate contract conformance
- Adapter CI validates model parity against the execution-engine commit pinned
  in `.github/workflows/ci.yml`. Suite release evidence must additionally bind
  the adapter and engine submodule commits selected by the integration repo.

## Non-Goals

- This file does not declare live-trading readiness.
- This file does not replace the integration repository's release evidence.
