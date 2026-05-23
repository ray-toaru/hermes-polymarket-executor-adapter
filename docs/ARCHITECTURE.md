# Hermes Polymarket Executor Adapter Architecture

## Role

`hermes-polymarket-executor-adapter` is the Hermes-compatible executor adapter.
It provides typed executor API clients, schema models, and safe report/tool
wrappers for Hermes-facing workflows.

## It May Own

- typed executor client calls
- Pydantic models aligned to the executor OpenAPI contract
- Hermes-compatible tool schema wrappers
- Hermes plugin registration for service/admin executor tools
- safe report rendering
- service/admin token separation
- no-secret static checks

## It Does Not

- own trading strategy
- own execution-engine risk policy
- sign orders
- hold private keys
- hold CLOB API secrets
- post directly to Polymarket
- cancel directly through Polymarket
- write to the execution engine database
- construct reusable signed order payloads

## Allowed Flow

```text
operator/tool input
  -> TradeIntent
  -> ExecutorClient.normalize_intent
  -> ExecutorClient.capture_snapshot
  -> ExecutorClient.evaluate_decision
  -> approval
  -> ExecutorClient.compile_plan
  -> ExecutorClient.submit_plan
```

## Admin Flow

Admin operations require an admin token and should be explicit in the UI/tooling.

Examples:

- cancel order
- trigger reconcile
- kill switch

## Future Hermes Integration

This package wraps selected `ExecutorClient` methods as Hermes plugin tools. The
integration preserves the same forbidden-data boundary and keeps admin tools in a
separate toolset with explicit admin token availability checks.

## MCP Position

MCP is not the primary integration path for this repository. A future MCP facade
may be added only when non-Hermes agents need the same executor adapter surface.
It must reuse the existing client/models and must not broaden the adapter's
authority.

## Versioning

This adapter may version independently from the execution engine after v0.26. A
suite release pins a tested adapter commit and execution-engine commit. The
adapter must document which executor API contract versions it supports.
