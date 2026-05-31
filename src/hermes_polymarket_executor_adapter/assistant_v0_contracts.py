from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


DRY_RUN_FIXED_EXECUTOR_MODE = "BLOCKED_DRY_RUN"

SAFE_SESSION_TOOLS = frozenset(
    {
        "create_user_thesis",
        "search_trade_expressions",
        "compare_trade_expressions",
        "draft_trade_plan",
        "risk_review_trade_plan",
        "record_operator_review_reference",
        "dry_run_trade_plan",
        "get_execution_status",
        "mark_dry_run_report_cancelled",
        "review_trade_outcome",
    }
)

ADAPTER_REQUIRED_TOOLS = frozenset(
    {
        "risk_review_trade_plan",
        "dry_run_trade_plan",
        "get_execution_status",
    }
)

ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER = frozenset(
    {
        "create_user_thesis",
        "search_trade_expressions",
        "compare_trade_expressions",
        "draft_trade_plan",
        "record_operator_review_reference",
        "mark_dry_run_report_cancelled",
        "review_trade_outcome",
    }
)

FORBIDDEN_TOOL_NAMES = frozenset(
    {
        "_".join(("sign", "order")),
        "_".join(("post", "order")),
        "_".join(("cancel", "live", "order")),
        "set_allowance",
        "transfer_funds",
        "create_api_key",
        "raw_clob_request",
        "direct_database_write",
        "approve_trade_plan",
    }
)


class AssistantV0Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RiskReviewTradePlanRequest(AssistantV0Model):
    plan_id: str = Field(min_length=1)
    policy_profile: Literal["dry_run_default", "dry_run_strict"] = "dry_run_default"


class RecordOperatorReviewReferenceRequest(AssistantV0Model):
    plan_id: str = Field(min_length=1)
    reviewed_by: str = Field(min_length=1)
    scope: Literal["DRY_RUN_REFERENCE_ONLY"]
    expires_at: datetime
    review_text: str = Field(min_length=1)


class DryRunTradePlanRequest(AssistantV0Model):
    plan_id: str = Field(min_length=1)
    review_reference_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)


class GetExecutionStatusRequest(AssistantV0Model):
    plan_id: str = Field(min_length=1)
    execution_id: str | None = None
    order_id: str | None = None


_REQUEST_MODELS: dict[str, type[AssistantV0Model]] = {
    "risk_review_trade_plan": RiskReviewTradePlanRequest,
    "record_operator_review_reference": RecordOperatorReviewReferenceRequest,
    "dry_run_trade_plan": DryRunTradePlanRequest,
    "get_execution_status": GetExecutionStatusRequest,
}


def validate_assistant_v0_tool_request(tool_name: str, payload: Any) -> tuple[str, ...]:
    """Validate the assistant-v0 safe tool contract without executor side effects."""

    if tool_name in FORBIDDEN_TOOL_NAMES:
        return (f"forbidden_tool:{tool_name}",)
    if tool_name not in SAFE_SESSION_TOOLS:
        return (f"unknown_tool:{tool_name}",)

    model = _REQUEST_MODELS.get(tool_name)
    if model is None:
        return ()

    violations: list[str] = []
    if tool_name == "dry_run_trade_plan" and isinstance(payload, dict) and "mode" in payload:
        violations.append("dry_run_trade_plan:mode_override")

    try:
        model.model_validate(payload)
    except ValidationError as exc:
        violations.extend(_validation_errors_to_contract_violations(tool_name, exc))

    return tuple(violations)


def assistant_v0_executor_mode_for(tool_name: str) -> str | None:
    if tool_name == "dry_run_trade_plan":
        return DRY_RUN_FIXED_EXECUTOR_MODE
    return None


def _validation_errors_to_contract_violations(
    tool_name: str,
    exc: ValidationError,
) -> tuple[str, ...]:
    violations: list[str] = []
    for error in exc.errors():
        loc = error.get("loc") or ("payload",)
        field = str(loc[0])
        error_type = str(error.get("type") or "invalid")
        if error_type == "missing":
            violations.append(f"schema_rejection:{tool_name}:missing_required:{field}")
        elif error_type == "extra_forbidden":
            violations.append(f"schema_rejection:{tool_name}:unexpected_field:{field}")
        elif error_type in {"literal_error", "enum"}:
            violations.append(f"schema_rejection:{tool_name}:enum:{field}")
        elif error_type == "string_too_short":
            violations.append(f"schema_rejection:{tool_name}:min_length:{field}")
        else:
            violations.append(f"schema_rejection:{tool_name}:{error_type}:{field}")
    return tuple(violations)
