from __future__ import annotations

from . import assistant_v0_facade
from . import hermes_handlers as handlers
from . import hermes_schemas as schemas


SERVICE_ENV = ["PM_EXEC_SERVICE_TOKEN"]
ADMIN_ENV = ["PM_EXEC_SERVICE_TOKEN", "PM_EXEC_ADMIN_TOKEN"]


def register(ctx) -> None:
    assistant_handlers = getattr(ctx, "assistant_v0_handlers", None)
    for spec in assistant_v0_facade.build_assistant_v0_tool_specs(assistant_handlers):
        _register_assistant_v0_tool(ctx, spec)

    _register_service_tool(
        ctx,
        "polymarket_executor_health",
        schemas.EXECUTOR_HEALTH_SCHEMA,
        handlers.handle_executor_health,
        "Check standalone Polymarket executor health.",
    )
    _register_service_tool(
        ctx,
        "polymarket_normalize_intent",
        schemas.NORMALIZE_INTENT_SCHEMA,
        handlers.handle_normalize_intent,
        "Normalize a Polymarket executor trade intent.",
    )
    _register_service_tool(
        ctx,
        "polymarket_capture_snapshot",
        schemas.CAPTURE_SNAPSHOT_SCHEMA,
        handlers.handle_capture_snapshot,
        "Capture an executor feasibility snapshot.",
    )
    _register_service_tool(
        ctx,
        "polymarket_evaluate_decision",
        schemas.EVALUATE_DECISION_SCHEMA,
        handlers.handle_evaluate_decision,
        "Evaluate executor constraints.",
    )
    _register_service_tool(
        ctx,
        "polymarket_compile_plan",
        schemas.COMPILE_PLAN_SCHEMA,
        handlers.handle_compile_plan,
        "Compile an executor plan summary after explicit approval.",
    )
    _register_service_tool(
        ctx,
        "polymarket_prepare_execution_plan",
        schemas.PREPARE_EXECUTION_PLAN_SCHEMA,
        handlers.handle_prepare_execution_plan,
        "Run the safe executor preparation sequence without submitting.",
    )
    _register_service_tool(
        ctx,
        "polymarket_get_submission",
        schemas.GET_SUBMISSION_SCHEMA,
        handlers.handle_get_submission,
        "Fetch an executor submission receipt.",
    )
    _register_service_tool(
        ctx,
        "polymarket_list_execution_lifecycle_events",
        schemas.LIST_EXECUTION_LIFECYCLE_EVENTS_SCHEMA,
        handlers.handle_list_execution_lifecycle_events,
        "List redacted executor lifecycle events.",
    )
    _register_service_tool(
        ctx,
        "polymarket_canary_report",
        schemas.CANARY_REPORT_SCHEMA,
        handlers.handle_canary_report,
        "Build a reference-only canary readiness report.",
    )
    _register_admin_tool(
        ctx,
        "polymarket_admin_kill_switch",
        schemas.ADMIN_KILL_SWITCH_SCHEMA,
        handlers.handle_admin_kill_switch,
        "Set executor kill switch through the admin API.",
    )
    _register_admin_tool(
        ctx,
        "polymarket_admin_cancel_order",
        schemas.ADMIN_CANCEL_ORDER_SCHEMA,
        handlers.handle_admin_cancel_order,
        "Request executor-admin cancellation for an order.",
    )
    _register_admin_tool(
        ctx,
        "polymarket_admin_reconcile",
        schemas.ADMIN_RECONCILE_SCHEMA,
        handlers.handle_admin_reconcile,
        "Trigger executor-admin reconciliation.",
    )
    _register_admin_tool(
        ctx,
        "polymarket_admin_list_audit_events",
        schemas.ADMIN_LIST_AUDIT_EVENTS_SCHEMA,
        handlers.handle_admin_list_audit_events,
        "List executor admin audit events.",
    )


def _register_service_tool(ctx, name: str, schema: dict, handler, description: str) -> None:
    ctx.register_tool(
        name=name,
        toolset="polymarket_executor",
        schema=schema,
        handler=handler,
        check_fn=handlers.check_executor_available,
        requires_env=SERVICE_ENV,
        description=description,
    )


def _register_admin_tool(ctx, name: str, schema: dict, handler, description: str) -> None:
    ctx.register_tool(
        name=name,
        toolset="polymarket_executor_admin",
        schema=schema,
        handler=handler,
        check_fn=handlers.check_admin_available,
        requires_env=ADMIN_ENV,
        description=description,
    )


def _register_assistant_v0_tool(
    ctx,
    spec: assistant_v0_facade.AssistantV0ToolSpec,
) -> None:
    ctx.register_tool(
        name=spec.name,
        toolset=assistant_v0_facade.ASSISTANT_V0_TOOLSET,
        schema=spec.schema,
        handler=spec.handler,
        check_fn=handlers.check_executor_available,
        requires_env=SERVICE_ENV,
        description=spec.description,
    )
