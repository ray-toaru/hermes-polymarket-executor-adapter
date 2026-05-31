from __future__ import annotations

import pytest

from hermes_polymarket_executor_adapter.assistant_v0_contracts import (
    ADAPTER_REQUIRED_TOOLS,
    ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER,
    DRY_RUN_FIXED_EXECUTOR_MODE,
    FORBIDDEN_TOOL_NAMES,
    SAFE_SESSION_TOOLS,
    DryRunTradePlanRequest,
    assistant_v0_executor_mode_for,
    validate_assistant_v0_tool_request,
)


def test_assistant_v0_contract_keeps_adapter_surface_narrow():
    assert ADAPTER_REQUIRED_TOOLS == {
        "risk_review_trade_plan",
        "dry_run_trade_plan",
        "get_execution_status",
    }
    assert ADAPTER_REQUIRED_TOOLS.issubset(SAFE_SESSION_TOOLS)
    assert "search_trade_expressions" in SAFE_SESSION_TOOLS
    assert "search_trade_expressions" in ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER
    assert "approve_trade_plan" not in SAFE_SESSION_TOOLS
    assert "approve_trade_plan" in FORBIDDEN_TOOL_NAMES


def test_dry_run_trade_plan_contract_has_no_caller_mode_or_approval_alias():
    schema = DryRunTradePlanRequest.model_json_schema()
    assert schema["required"] == ["plan_id", "review_reference_id", "idempotency_key"]
    assert "mode" not in schema["properties"]
    assert "approval_id" not in schema["properties"]
    assert assistant_v0_executor_mode_for("dry_run_trade_plan") == DRY_RUN_FIXED_EXECUTOR_MODE
    assert DRY_RUN_FIXED_EXECUTOR_MODE == "BLOCKED_DRY_RUN"


@pytest.mark.parametrize(
    ("tool_name", "payload", "expected_violations"),
    [
        (
            "dry_run_trade_plan",
            {
                "plan_id": "plan-fixture-001",
                "review_reference_id": "review-reference-fixture-001",
                "idempotency_key": "conformance-valid-dry-run-001",
            },
            (),
        ),
        (
            "dry_run_trade_plan",
            {
                "plan_id": "plan-fixture-001",
                "review_reference_id": "review-reference-fixture-001",
                "idempotency_key": "conformance-mode-override-001",
                "mode": "LIVE",
            },
            (
                "dry_run_trade_plan:mode_override",
                "schema_rejection:dry_run_trade_plan:unexpected_field:mode",
            ),
        ),
        (
            "dry_run_trade_plan",
            {
                "plan_id": "plan-fixture-001",
                "approval_id": "approval-fixture-001",
                "idempotency_key": "conformance-approval-alias-001",
            },
            (
                "schema_rejection:dry_run_trade_plan:missing_required:review_reference_id",
                "schema_rejection:dry_run_trade_plan:unexpected_field:approval_id",
            ),
        ),
        (
            "record_operator_review_reference",
            {
                "plan_id": "plan-fixture-001",
                "reviewed_by": "operator-fixture-001",
                "scope": "LIVE_SUBMIT",
                "expires_at": "2026-05-23T08:00:00Z",
                "review_text": "Unsafe scope must be rejected.",
            },
            ("schema_rejection:record_operator_review_reference:enum:scope",),
        ),
        (
            "approve_trade_plan",
            {"plan_id": "plan-fixture-001"},
            ("forbidden_tool:approve_trade_plan",),
        ),
        (
            "post_order",
            {"plan_id": "plan-fixture-001"},
            ("forbidden_tool:post_order",),
        ),
        (
            "raw_clob_request",
            {"method": "POST", "path": "/order"},
            ("forbidden_tool:raw_clob_request",),
        ),
    ],
)
def test_assistant_v0_contract_request_cases(tool_name, payload, expected_violations):
    assert validate_assistant_v0_tool_request(tool_name, payload) == expected_violations
