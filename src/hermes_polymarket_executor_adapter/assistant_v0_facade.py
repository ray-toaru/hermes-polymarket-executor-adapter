from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .assistant_v0_contracts import (
    ADAPTER_REQUIRED_TOOLS,
    ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER,
    DRY_RUN_FIXED_EXECUTOR_MODE,
    DryRunTradePlanRequest,
    GetExecutionStatusRequest,
    RiskReviewTradePlanRequest,
    assistant_v0_executor_mode_for,
    validate_assistant_v0_tool_request,
)
from .assistant_v0_manifest_loader import load_assistant_v0_contracts_from_objects


ASSISTANT_V0_TOOLSET = "polymarket_assistant_v0"


@dataclass(frozen=True)
class AssistantV0ToolSpec:
    name: str
    schema: dict[str, Any]
    handler: Callable[..., str]
    description: str


class AssistantV0Facade:
    def __init__(self, handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None):
        self._handlers = {
            "risk_review_trade_plan": _handle_risk_review_trade_plan,
            "dry_run_trade_plan": _handle_dry_run_trade_plan,
            "get_execution_status": _handle_get_execution_status,
        }
        if handlers:
            self._handlers.update(handlers)

    def dispatch(self, tool_name: str, payload: Any) -> dict[str, Any]:
        violations = validate_assistant_v0_tool_request(tool_name, payload)
        if violations:
            return {
                "ok": False,
                "tool_name": tool_name,
                "code": "CONTRACT_VIOLATION",
                "violations": list(violations),
                "executor_called": False,
                "submitted_live": False,
            }

        if tool_name in ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER:
            return {
                "ok": False,
                "tool_name": tool_name,
                "code": "LOCAL_ASSISTANT_TOOL",
                "message": (
                    f"{tool_name} is owned by the assistant runtime; "
                    "operator review references are not executable authorization."
                ),
                "executor_called": False,
                "submitted_live": False,
            }

        handler = self._handlers.get(tool_name)
        if handler is None:
            return {
                "ok": False,
                "tool_name": tool_name,
                "code": "UNSUPPORTED_ADAPTER_TOOL",
                "message": f"{tool_name} is not implemented by the assistant-v0 adapter facade.",
                "executor_called": False,
                "submitted_live": False,
            }

        if not isinstance(payload, dict):
            payload = {}
        return handler(payload)


def build_assistant_v0_tool_specs(
    handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
) -> tuple[AssistantV0ToolSpec, ...]:
    facade = AssistantV0Facade(handlers=handlers)
    specs = tuple(
        AssistantV0ToolSpec(
            name=name,
            schema=_ASSISTANT_V0_SCHEMAS[name],
            handler=_bound_handler(facade, name),
            description=_DESCRIPTIONS[name],
        )
        for name in sorted(ADAPTER_REQUIRED_TOOLS)
    )
    load_assistant_v0_contracts_from_objects(
        _assistant_v0_manifest(specs),
        _assistant_v0_conformance(),
    )
    return specs


def _bound_handler(facade: AssistantV0Facade, tool_name: str) -> Callable[..., str]:
    def handler(args: dict | None = None, **_kwargs) -> str:
        return _json_result(facade.dispatch(tool_name, args or {}))

    return handler


def handle_risk_review_trade_plan(args: dict, **_kwargs) -> str:
    return _json_result(AssistantV0Facade().dispatch("risk_review_trade_plan", args))


def handle_dry_run_trade_plan(args: dict, **_kwargs) -> str:
    return _json_result(AssistantV0Facade().dispatch("dry_run_trade_plan", args))


def handle_get_execution_status(args: dict, **_kwargs) -> str:
    return _json_result(AssistantV0Facade().dispatch("get_execution_status", args))


def _handle_risk_review_trade_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(payload["plan_id"])
    return {
        "ok": False,
        "tool_name": "risk_review_trade_plan",
        "code": "STUB_NOT_BOUND",
        "kind": "RiskReview",
        "executor_called": False,
        "submitted_live": False,
        "payload": {
            "risk_review_id": f"risk-review:assistant-v0:{plan_id}",
            "plan_id": plan_id,
            "created_at": _now_utc(),
            "decision": "LIVE_READINESS_BLOCKED",
            "blocked_rules": ["assistant_v0_facade_stub_no_executor_binding"],
            "warnings": ["adapter facade is not yet bound to executor dry-run APIs"],
            "max_loss_usdc": None,
            "requires_operator_review": True,
            "executor_refs": {
                "normalized_intent_id": None,
                "snapshot_id": None,
                "decision_id": None,
                "plan_hash": None,
            },
        },
    }


def _handle_dry_run_trade_plan(payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(payload["plan_id"])
    return {
        "ok": False,
        "tool_name": "dry_run_trade_plan",
        "code": "STUB_NOT_BOUND",
        "kind": "DryRunResult",
        "executor_mode": assistant_v0_executor_mode_for("dry_run_trade_plan"),
        "executor_called": False,
        "submitted_live": False,
        "payload": {
            "dry_run_id": f"dry-run:assistant-v0:{plan_id}",
            "plan_id": plan_id,
            "created_at": _now_utc(),
            "status": "BLOCKED",
            "submitted_live": False,
            "receipt_ref": None,
            "validation_errors": ["assistant_v0_facade_stub_no_executor_binding"],
            "dry_run_reports": [],
        },
    }


def _handle_get_execution_status(payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = str(payload["plan_id"])
    return {
        "ok": False,
        "tool_name": "get_execution_status",
        "code": "STUB_NOT_BOUND",
        "kind": "ExecutionStatus",
        "executor_called": False,
        "submitted_live": False,
        "payload": {
            "status_id": f"status:assistant-v0:{plan_id}",
            "plan_id": plan_id,
            "observed_at": _now_utc(),
            "source": "adapter_dry_run",
            "state": "UNKNOWN",
            "events": [],
        },
    }


def _json_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_schema(model: Any, description: str) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema["description"] = description
    return {"description": description, "parameters": schema}


def _assistant_v0_manifest(specs: tuple[AssistantV0ToolSpec, ...]) -> dict[str, Any]:
    return {
        "name": "polymarket-trading-assistant-v0-safe-tools",
        "version": "0.28.0",
        "tools": [
            {
                "name": spec.name,
                "input_schema": spec.schema["parameters"],
                **(
                    {
                        "fixed_executor_mode": DRY_RUN_FIXED_EXECUTOR_MODE,
                        "allow_mode_override": False,
                    }
                    if spec.name == "dry_run_trade_plan"
                    else {}
                ),
            }
            for spec in specs
        ],
        "forbidden_effects": ["approve_trade_plan", "post_order", "raw_clob_request"],
    }


def _assistant_v0_conformance() -> dict[str, Any]:
    from .assistant_v0_contracts import (
        ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER,
        FORBIDDEN_TOOL_NAMES,
        SAFE_SESSION_TOOLS,
    )

    return {
        "contract_version": "assistant-v0",
        "target_component": "hermes-polymarket-executor-adapter",
        "safe_session_tools": sorted(SAFE_SESSION_TOOLS),
        "adapter_required_tools": sorted(ADAPTER_REQUIRED_TOOLS),
        "forbidden_tool_names": sorted(FORBIDDEN_TOOL_NAMES),
        "dry_run_executor_mode_contract": {
            "tool": "dry_run_trade_plan",
            "fixed_executor_mode": DRY_RUN_FIXED_EXECUTOR_MODE,
            "allow_mode_override": False,
        },
        "assistant_local_tools_not_required_from_adapter": sorted(
            ASSISTANT_LOCAL_TOOLS_NOT_REQUIRED_FROM_ADAPTER
        ),
    }


_DESCRIPTIONS = {
    "risk_review_trade_plan": "Review a bounded assistant-v0 trade plan through non-live adapter checks.",
    "dry_run_trade_plan": (
        "Run a dry-run-compatible assistant-v0 plan using a review reference; "
        f"executor mode is fixed to {DRY_RUN_FIXED_EXECUTOR_MODE}."
    ),
    "get_execution_status": "Read assistant-v0 execution status without live side effects.",
}

_ASSISTANT_V0_SCHEMAS = {
    "risk_review_trade_plan": _request_schema(
        RiskReviewTradePlanRequest,
        _DESCRIPTIONS["risk_review_trade_plan"],
    ),
    "dry_run_trade_plan": _request_schema(
        DryRunTradePlanRequest,
        _DESCRIPTIONS["dry_run_trade_plan"],
    ),
    "get_execution_status": _request_schema(
        GetExecutionStatusRequest,
        _DESCRIPTIONS["get_execution_status"],
    ),
}
