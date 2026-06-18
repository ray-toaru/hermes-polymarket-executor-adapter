from __future__ import annotations

from .models import (
    ApprovalReceipt,
    CanaryApprovalReference,
    CanaryEvidenceReference,
    ConstraintDecision,
    FeasibilitySnapshot,
    NormalizedIntent,
    TradeIntent,
)


def _object_schema(description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        },
    }


def _model_property_schema(model, description: str) -> dict:
    schema = model.model_json_schema()
    schema["description"] = description
    return schema


CORRELATION_ID = {
    "type": "string",
    "description": "Optional executor correlation id for audit and traceability.",
}


EXECUTOR_HEALTH_SCHEMA = _object_schema(
    "Check the standalone Polymarket executor health through its service API.",
    {},
)

NORMALIZE_INTENT_SCHEMA = _object_schema(
    "Normalize a TradeIntent through the executor service API.",
    {
        "intent": _model_property_schema(
            TradeIntent,
            "TradeIntent payload matching the executor public schema.",
        )
    },
    ["intent"],
)

CAPTURE_SNAPSHOT_SCHEMA = _object_schema(
    "Capture a feasibility snapshot for a normalized intent.",
    {
        "normalized": _model_property_schema(
            NormalizedIntent,
            "NormalizedIntent payload returned by polymarket_normalize_intent.",
        )
    },
    ["normalized"],
)

EVALUATE_DECISION_SCHEMA = _object_schema(
    "Evaluate executor constraints for a normalized intent and feasibility snapshot.",
    {
        "normalized": _model_property_schema(
            NormalizedIntent, "NormalizedIntent payload."
        ),
        "snapshot": _model_property_schema(
            FeasibilitySnapshot, "FeasibilitySnapshot payload."
        ),
    },
    ["normalized", "snapshot"],
)

COMPILE_PLAN_SCHEMA = _object_schema(
    "Compile an executor plan summary after explicit approval.",
    {
        "normalized": _model_property_schema(
            NormalizedIntent, "NormalizedIntent payload."
        ),
        "snapshot": _model_property_schema(
            FeasibilitySnapshot, "FeasibilitySnapshot payload."
        ),
        "decision": _model_property_schema(
            ConstraintDecision, "ConstraintDecision payload."
        ),
        "approval": _model_property_schema(
            ApprovalReceipt, "ApprovalReceipt payload."
        ),
    },
    ["normalized", "snapshot", "decision", "approval"],
)

PREPARE_EXECUTION_PLAN_SCHEMA = _object_schema(
    "Run the safe executor preparation sequence: normalize, snapshot, evaluate, compile. It does not submit.",
    {
        "intent": _model_property_schema(
            TradeIntent,
            "TradeIntent payload matching the executor public schema.",
        ),
        "approval": _model_property_schema(
            ApprovalReceipt,
            "ApprovalReceipt payload required before plan compilation.",
        ),
    },
    ["intent", "approval"],
)

GET_SUBMISSION_SCHEMA = _object_schema(
    "Fetch a previously recorded executor submission receipt.",
    {
        "execution_id": {"type": "string", "description": "Executor execution id."},
    },
    ["execution_id"],
)

LIST_EXECUTION_LIFECYCLE_EVENTS_SCHEMA = _object_schema(
    "List redacted executor lifecycle events for one execution.",
    {
        "execution_id": {"type": "string", "description": "Executor execution id."},
        "limit": {"type": "integer", "minimum": 1},
        "before_event_id": {"type": "integer", "minimum": 1},
        "correlation_id": CORRELATION_ID,
    },
    ["execution_id"],
)

CANARY_REPORT_SCHEMA = _object_schema(
    "Build a local reference-only canary readiness report. This never authorizes live submit.",
    {
        "evidence": _model_property_schema(
            CanaryEvidenceReference, "CanaryEvidenceReference payload."
        ),
        "approval": _model_property_schema(
            CanaryApprovalReference, "Optional CanaryApprovalReference payload."
        ),
        "blocked_reasons": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Reasons the report remains blocked.",
        },
    },
    ["evidence"],
)

ADMIN_KILL_SWITCH_SCHEMA = _object_schema(
    "Set the executor kill switch through the admin API.",
    {
        "account_id": {"type": "string", "description": "Account id for ACCOUNT scope."},
        "enabled": {"type": "boolean"},
        "reason": {"type": "string", "description": "Required human-readable admin reason."},
        "scope": {"type": "string", "enum": ["ACCOUNT", "GLOBAL"]},
    },
    ["enabled", "reason"],
)

ADMIN_CANCEL_ORDER_SCHEMA = _object_schema(
    "Request executor-admin cancellation for an order. This does not call Polymarket directly.",
    {
        "account_id": {"type": "string"},
        "order_id": {"type": "string"},
        "reason": {"type": "string", "description": "Required human-readable admin reason."},
        "execution_id": {"type": "string"},
        "correlation_id": CORRELATION_ID,
    },
    ["account_id", "order_id", "reason"],
)

ADMIN_RECONCILE_SCHEMA = _object_schema(
    "Trigger executor-admin reconciliation for an account.",
    {
        "account_id": {"type": "string"},
        "reason": {"type": "string", "description": "Required human-readable admin reason."},
        "execution_id": {"type": "string"},
        "correlation_id": CORRELATION_ID,
    },
    ["account_id", "reason"],
)

ADMIN_LIST_AUDIT_EVENTS_SCHEMA = _object_schema(
    "List executor admin audit events with optional filters.",
    {
        "limit": {"type": "integer", "minimum": 1},
        "before_audit_id": {"type": "integer", "minimum": 1},
        "operation": {"type": "string"},
        "principal_subject": {"type": "string"},
        "result": {"type": "string"},
        "audit_correlation_id": {"type": "string"},
        "correlation_id": CORRELATION_ID,
    },
)

ADMIN_LIST_LIVE_READ_EVENTS_SCHEMA = _object_schema(
    "List read-only normalized live-read events with optional filters.",
    {
        "limit": {"type": "integer", "minimum": 1},
        "before_event_id": {"type": "integer", "minimum": 1},
        "account_id": {"type": "string"},
        "operation": {
            "type": "string",
            "enum": ["GET_ORDER", "LIST_OPEN_ORDERS", "LIST_FILLS", "LIST_POSITIONS"],
        },
        "outcome": {
            "type": "string",
            "enum": [
                "OBSERVED",
                "MISSING",
                "BLOCKED",
                "REMOTE_REJECTED",
                "REMOTE_UNKNOWN",
                "AUTHENTICATION_FAILED",
            ],
        },
        "remote_order_id": {"type": "string"},
        "correlation_id": CORRELATION_ID,
    },
)
