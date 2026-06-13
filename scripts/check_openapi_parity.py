#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from hermes_polymarket_executor_adapter import models


MODEL_BY_SCHEMA = {
    "MarketRef": "MarketRef",
    "QuantityIntent": "QuantityIntent",
    "TradeIntent": "TradeIntent",
    "NormalizedIntent": "NormalizedIntent",
    "RuntimeStateSummary": "RuntimeStateSummary",
    "FeasibilitySnapshot": "FeasibilitySnapshot",
    "ConstraintDecision": "ConstraintDecision",
    "ApprovalReceipt": "ApprovalReceipt",
    "ExecutionPlanSummary": "ExecutionPlanSummary",
    "SubmitReceipt": "SubmitReceipt",
    "CancelReceipt": "CancelReceipt",
    "KillSwitchReceipt": "KillSwitchReceipt",
    "ReconcileReport": "ReconcileReport",
    "OrderLifecycleRecord": "OrderLifecycleRecord",
    "OrderLifecycleDivergence": "OrderLifecycleDivergence",
    "ReconcileOrderLocalResponse": "ReconcileOrderLocalResponse",
    "SignOnlyLifecycleRecord": "SignOnlyLifecycleRecord",
    "StandardSignOnlyConstructionRequest": "StandardSignOnlyConstructionRequest",
    "StandardSignOnlyConstructionReceipt": "StandardSignOnlyConstructionReceipt",
    "RedactedPayloadEnvelope": "RedactedPayloadEnvelope",
    "ExecutionLifecycleEvent": "ExecutionLifecycleEvent",
    "AdminAuditEvent": "AdminAuditEvent",
    "HealthReport": "HealthReport",
}


def load_spec(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("OpenAPI document must be an object")
    return value


def parity_failures(spec: dict[str, Any]) -> list[str]:
    schemas = spec.get("components", {}).get("schemas", {})
    failures: list[str] = []
    for schema_name, model_name in MODEL_BY_SCHEMA.items():
        schema = schemas.get(schema_name)
        if not isinstance(schema, dict):
            failures.append(f"OpenAPI schema missing: {schema_name}")
            continue
        model = getattr(models, model_name)
        model_schema = model.model_json_schema()
        expected_fields = set(schema.get("properties", {}))
        actual_fields = set(model.model_fields)
        if actual_fields != expected_fields:
            failures.append(
                f"{model_name} fields {sorted(actual_fields)} != "
                f"{schema_name} fields {sorted(expected_fields)}"
            )
        expected_required = set(schema.get("required", []))
        actual_required = set(model_schema.get("required", []))
        if actual_required != expected_required:
            failures.append(
                f"{model_name} required fields {sorted(actual_required)} != "
                f"{schema_name} required fields {sorted(expected_required)}"
            )
        if model_schema.get("additionalProperties") != schema.get("additionalProperties"):
            failures.append(
                f"{model_name} additionalProperties "
                f"{model_schema.get('additionalProperties')} != "
                f"{schema_name} additionalProperties {schema.get('additionalProperties')}"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate adapter Pydantic models against executor.v1 OpenAPI schemas."
    )
    parser.add_argument("openapi", type=Path)
    args = parser.parse_args(argv)

    failures = parity_failures(load_spec(args.openapi))
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print(f"OpenAPI model parity check passed: {len(MODEL_BY_SCHEMA)} schemas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
