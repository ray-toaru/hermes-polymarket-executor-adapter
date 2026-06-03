from __future__ import annotations

from hermes_polymarket_executor_adapter.assistant_v0_contracts import (
    DryRunTradePlanRequest,
    GetExecutionStatusRequest,
    RiskReviewTradePlanRequest,
)
from hermes_polymarket_executor_adapter.assistant_v0_facade import (
    _ASSISTANT_V0_SCHEMAS,
    build_assistant_v0_tool_specs,
)
from hermes_polymarket_executor_adapter.hermes_schemas import (
    CAPTURE_SNAPSHOT_SCHEMA,
    COMPILE_PLAN_SCHEMA,
    EVALUATE_DECISION_SCHEMA,
    NORMALIZE_INTENT_SCHEMA,
    PREPARE_EXECUTION_PLAN_SCHEMA,
)


def test_executor_tool_schemas_expose_nested_object_contracts():
    expected = {
        "intent": NORMALIZE_INTENT_SCHEMA,
        "normalized": CAPTURE_SNAPSHOT_SCHEMA,
    }
    for field, schema in expected.items():
        nested = schema["parameters"]["properties"][field]
        assert schema["parameters"]["additionalProperties"] is False
        assert field in schema["parameters"]["required"]
        assert nested["type"] == "object"
        assert nested["additionalProperties"] is False
        assert nested["required"]

    nested_pairs = [
        (EVALUATE_DECISION_SCHEMA, ("normalized", "snapshot")),
        (COMPILE_PLAN_SCHEMA, ("normalized", "snapshot", "decision", "approval")),
        (PREPARE_EXECUTION_PLAN_SCHEMA, ("intent", "approval")),
    ]
    for schema, fields in nested_pairs:
        assert schema["parameters"]["additionalProperties"] is False
        assert schema["parameters"]["required"] == list(fields)
        for field in fields:
            nested = schema["parameters"]["properties"][field]
            assert nested["type"] == "object"
            assert nested["additionalProperties"] is False
            assert nested["required"]


def test_assistant_v0_tool_schemas_are_generated_from_request_models():
    expected = {
        "risk_review_trade_plan": RiskReviewTradePlanRequest.model_json_schema(),
        "dry_run_trade_plan": DryRunTradePlanRequest.model_json_schema(),
        "get_execution_status": GetExecutionStatusRequest.model_json_schema(),
    }
    for tool_name, model_schema in expected.items():
        parameters = dict(_ASSISTANT_V0_SCHEMAS[tool_name]["parameters"])
        assert parameters.pop("description") == _ASSISTANT_V0_SCHEMAS[tool_name]["description"]
        assert parameters == model_schema


def test_assistant_v0_manifest_uses_generated_request_schemas():
    specs = build_assistant_v0_tool_specs()
    manifest_tools = {}
    for spec in specs:
        parameters = dict(spec.schema["parameters"])
        parameters.pop("description")
        manifest_tools[spec.name] = parameters
    assert manifest_tools == {
        "dry_run_trade_plan": DryRunTradePlanRequest.model_json_schema(),
        "get_execution_status": GetExecutionStatusRequest.model_json_schema(),
        "risk_review_trade_plan": RiskReviewTradePlanRequest.model_json_schema(),
    }
