from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.parse import urlparse

from pydantic import BaseModel, ValidationError

from .client import ExecutorClient, ExecutorHttpError
from .config import ExecutorConfig
from .models import (
    ApprovalReceipt,
    CanaryApprovalReference,
    CanaryEvidenceReference,
    ConstraintDecision,
    FeasibilitySnapshot,
    NormalizedIntent,
    TradeIntent,
)
from .tools import build_canary_readiness_report


def check_executor_available() -> bool:
    return bool(os.environ.get("PM_EXEC_SERVICE_TOKEN") and _is_absolute_http_url(os.environ.get("PM_EXEC_SERVICE_URL")))


def check_admin_available() -> bool:
    return bool(
        check_executor_available()
        and os.environ.get("PM_EXEC_ADMIN_TOKEN")
        and os.environ.get("PM_EXEC_ADMIN_SUBJECT")
    )


def check_assistant_v0_available() -> bool:
    return True


def _is_absolute_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _result(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _error(message: str, *, code: str | None = None) -> str:
    payload = {"error": message}
    if code is not None:
        payload["code"] = code
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _validate(model: type[BaseModel], payload: Any):
    return model.model_validate(payload)


def _with_client(fn: Callable[[ExecutorClient], Any]) -> str:
    client: ExecutorClient | None = None
    try:
        client = ExecutorClient(ExecutorConfig.from_env())
        return _result(fn(client))
    except ExecutorHttpError as exc:
        payload = {"error": str(exc), "status_code": exc.status_code}
        if exc.code is not None:
            payload["code"] = exc.code
        if exc.correlation_id is not None:
            payload["correlation_id"] = exc.correlation_id
        return _result(payload)
    except (PermissionError, RuntimeError, ValidationError, ValueError) as exc:
        return _error(str(exc), code=_error_code_for_exception(exc))
    finally:
        if client is not None:
            client.close()


def _error_code_for_exception(exc: Exception) -> str:
    message = str(exc)
    if "PM_EXEC_SERVICE_URL is required" in message:
        return "CONFIG_MISSING_SERVICE_URL"
    if "PM_EXEC_SERVICE_TOKEN is required" in message:
        return "CONFIG_MISSING_SERVICE_TOKEN"
    if "PM_EXEC_ADMIN_SUBJECT is required" in message:
        return "CONFIG_MISSING_ADMIN_SUBJECT"
    if isinstance(exc, PermissionError):
        return "PERMISSION_DENIED"
    if isinstance(exc, ValidationError):
        return "VALIDATION_ERROR"
    return "EXECUTOR_ADAPTER_ERROR"


def _required_text(args: dict, key: str) -> str | None:
    value = args.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def handle_executor_health(args: dict, **_kwargs) -> str:
    return _with_client(lambda client: client.health())


def handle_normalize_intent(args: dict, **_kwargs) -> str:
    try:
        intent = _validate(TradeIntent, args["intent"])
    except KeyError:
        return _error("intent is required")
    except ValidationError as exc:
        return _error(str(exc))
    return _with_client(lambda client: client.normalize_intent(intent))


def handle_capture_snapshot(args: dict, **_kwargs) -> str:
    try:
        normalized = _validate(NormalizedIntent, args["normalized"])
    except KeyError:
        return _error("normalized is required")
    except ValidationError as exc:
        return _error(str(exc))
    return _with_client(lambda client: client.capture_snapshot(normalized))


def handle_evaluate_decision(args: dict, **_kwargs) -> str:
    try:
        normalized = _validate(NormalizedIntent, args["normalized"])
        snapshot = _validate(FeasibilitySnapshot, args["snapshot"])
    except KeyError as exc:
        return _error(f"{exc.args[0]} is required")
    except ValidationError as exc:
        return _error(str(exc))
    return _with_client(lambda client: client.evaluate_decision(normalized, snapshot))


def handle_compile_plan(args: dict, **_kwargs) -> str:
    try:
        normalized = _validate(NormalizedIntent, args["normalized"])
        snapshot = _validate(FeasibilitySnapshot, args["snapshot"])
        decision = _validate(ConstraintDecision, args["decision"])
        approval = _validate(ApprovalReceipt, args["approval"])
    except KeyError as exc:
        return _error(f"{exc.args[0]} is required")
    except ValidationError as exc:
        return _error(str(exc))
    if approval.approval_scope == "LIVE_SUBMIT":
        return _error("LIVE_SUBMIT approval_scope is not accepted by Hermes-facing adapter tools")
    return _with_client(lambda client: client.compile_plan(normalized, snapshot, decision, approval))


def handle_prepare_execution_plan(args: dict, **_kwargs) -> str:
    try:
        intent = _validate(TradeIntent, args["intent"])
        approval = _validate(ApprovalReceipt, args["approval"])
    except KeyError as exc:
        return _error(f"{exc.args[0]} is required")
    except ValidationError as exc:
        return _error(str(exc))
    if approval.approval_scope == "LIVE_SUBMIT":
        return _error("LIVE_SUBMIT approval_scope is not accepted by Hermes-facing adapter tools")

    def prepare(client: ExecutorClient):
        normalized = client.normalize_intent(intent)
        snapshot = client.capture_snapshot(normalized)
        decision = client.evaluate_decision(normalized, snapshot)
        return client.compile_plan(normalized, snapshot, decision, approval)

    return _with_client(prepare)


def handle_get_submission(args: dict, **_kwargs) -> str:
    execution_id = _required_text(args, "execution_id")
    if execution_id is None:
        return _error("execution_id is required")
    return _with_client(lambda client: client.get_submission(execution_id))


def handle_list_execution_lifecycle_events(args: dict, **_kwargs) -> str:
    execution_id = _required_text(args, "execution_id")
    if execution_id is None:
        return _error("execution_id is required")
    return _with_client(
        lambda client: client.list_execution_lifecycle_events(
            execution_id,
            limit=args.get("limit"),
            before_event_id=args.get("before_event_id"),
            correlation_id=args.get("correlation_id"),
        )
    )


def handle_canary_report(args: dict, **_kwargs) -> str:
    try:
        evidence = _validate(CanaryEvidenceReference, args["evidence"])
        approval = None
        if args.get("approval") is not None:
            approval = _validate(CanaryApprovalReference, args["approval"])
        report = build_canary_readiness_report(
            evidence,
            approval=approval,
            blocked_reasons=args.get("blocked_reasons"),
        )
    except KeyError:
        return _error("evidence is required")
    except ValidationError as exc:
        return _error(str(exc))
    return _result(report)


def handle_admin_kill_switch(args: dict, **_kwargs) -> str:
    reason = _required_text(args, "reason")
    if reason is None:
        return _error("reason is required")
    if args.get("enabled") is None:
        return _error("enabled is required")
    if not isinstance(args.get("enabled"), bool):
        return _error("enabled must be a boolean")
    scope = str(args.get("scope") or "ACCOUNT")
    account_id = args.get("account_id")
    if scope == "ACCOUNT" and not account_id:
        return _error("account_id is required for ACCOUNT scope")
    if scope == "GLOBAL":
        account_id = None
    return _with_client(
        lambda client: _verified_admin_call(
            client,
            {"KILL_SWITCH"},
            args.get("correlation_id"),
            lambda: client.set_kill_switch(
                account_id,
                args["enabled"],
                reason,
                scope=scope,
            ),
        )
    )


def handle_admin_cancel_order(args: dict, **_kwargs) -> str:
    account_id = _required_text(args, "account_id")
    order_id = _required_text(args, "order_id")
    reason = _required_text(args, "reason")
    if account_id is None:
        return _error("account_id is required")
    if order_id is None:
        return _error("order_id is required")
    if reason is None:
        return _error("reason is required")
    return _with_client(
        lambda client: _verified_admin_call(
            client,
            {"CANCEL_ORDER"},
            args.get("correlation_id"),
            lambda: client.cancel_order(
                account_id,
                order_id,
                reason,
                execution_id=args.get("execution_id"),
                correlation_id=args.get("correlation_id"),
            ),
        )
    )


def handle_admin_reconcile(args: dict, **_kwargs) -> str:
    account_id = _required_text(args, "account_id")
    reason = _required_text(args, "reason")
    if account_id is None:
        return _error("account_id is required")
    if reason is None:
        return _error("reason is required")
    return _with_client(
        lambda client: _verified_admin_call(
            client,
            {"RECONCILE"},
            args.get("correlation_id"),
            lambda: client.reconcile(
                account_id,
                reason,
                execution_id=args.get("execution_id"),
                correlation_id=args.get("correlation_id"),
            ),
        )
    )


def handle_admin_list_audit_events(args: dict, **_kwargs) -> str:
    return _with_client(
        lambda client: _verified_admin_call(
            client,
            {"READ_AUDIT"},
            args.get("correlation_id"),
            lambda: client.list_admin_audit_events(
                limit=args.get("limit"),
                before_audit_id=args.get("before_audit_id"),
                operation=args.get("operation"),
                principal_subject=args.get("principal_subject"),
                result=args.get("result"),
                audit_correlation_id=args.get("audit_correlation_id"),
                correlation_id=args.get("correlation_id"),
            ),
        )
    )


def _verified_admin_call(
    client: ExecutorClient,
    required_capabilities: set[str],
    correlation_id: str | None,
    operation: Callable[[], Any],
) -> Any:
    expected_subject = os.environ.get("PM_EXEC_ADMIN_SUBJECT")
    if not expected_subject:
        raise RuntimeError("PM_EXEC_ADMIN_SUBJECT is required")
    client.verify_admin_session(
        expected_subject=expected_subject,
        required_capabilities=required_capabilities,
        correlation_id=correlation_id,
    )
    return operation()
