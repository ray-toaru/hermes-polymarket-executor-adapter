# Hermes Polymarket Control Architecture

## Role

`hermes-polymarket-control` is the Hermes-facing control project. It produces intents, collects approvals, calls the execution engine, and renders reports.

## It Does Not

- sign orders
- hold private keys
- hold CLOB API secrets
- post directly to Polymarket
- cancel directly through Polymarket
- write to the execution engine database
- construct reusable signed order payloads

## Allowed Flow

```text
strategy/operator input
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

This package can later wrap the `ExecutorClient` methods as Hermes tools. That integration should still preserve the same forbidden-data boundary.
