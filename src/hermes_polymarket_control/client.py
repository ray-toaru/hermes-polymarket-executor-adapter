from __future__ import annotations

from typing import Any

import httpx

from .config import ExecutorConfig
from .models import (
    AdminAuditEvent,
    ApprovalReceipt,
    CancelReceipt,
    ConstraintDecision,
    ExecutionLifecycleEvent,
    ExecutionPlanSummary,
    FeasibilitySnapshot,
    HealthReport,
    KillSwitchReceipt,
    NormalizedIntent,
    ReconcileReport,
    SignOnlyLifecycleRecord,
    SubmitReceipt,
    TradeIntent,
)


class ExecutorClient:
    """Typed client for the standalone execution engine.

    This class deliberately has no signing, raw CLOB, raw signed order, or database methods.
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config
        self._client = httpx.Client(timeout=config.timeout_seconds)

    def __enter__(self) -> "ExecutorClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _headers(self, *, admin: bool = False, correlation_id: str | None = None) -> dict[str, str]:
        token = self.config.admin_token if admin else self.config.service_token
        if admin and not token:
            raise PermissionError("admin token is required for this operation")
        if not token:
            raise PermissionError("service token is required for this operation")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        if correlation_id:
            headers["X-Correlation-Id"] = correlation_id
        return headers

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        admin: bool = False,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"{self.config.base_url}{path}",
            json=payload,
            headers=self._headers(admin=admin, correlation_id=correlation_id),
        )
        response.raise_for_status()
        return response.json()

    def _get(
        self,
        path: str,
        *,
        admin: bool = False,
        params: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "headers": self._headers(admin=admin, correlation_id=correlation_id),
        }
        if params:
            kwargs["params"] = params
        response = self._client.get(f"{self.config.base_url}{path}", **kwargs)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _query_params(**values: Any) -> dict[str, Any]:
        return {key: value for key, value in values.items() if value is not None}

    def health(self) -> HealthReport:
        return HealthReport.model_validate(self._get("/v1/health"))

    def normalize_intent(self, intent: TradeIntent) -> NormalizedIntent:
        return NormalizedIntent.model_validate(
            self._post("/v1/intents/normalize", intent.model_dump(mode="json"))
        )

    def capture_snapshot(self, normalized: NormalizedIntent) -> FeasibilitySnapshot:
        return FeasibilitySnapshot.model_validate(
            self._post("/v1/snapshots/capture", normalized.model_dump(mode="json"))
        )

    def evaluate_decision(
        self,
        normalized: NormalizedIntent,
        snapshot: FeasibilitySnapshot,
    ) -> ConstraintDecision:
        return ConstraintDecision.model_validate(
            self._post(
                "/v1/decisions/evaluate",
                {
                    "normalized_intent_id": normalized.normalized_intent_id,
                    "snapshot_id": snapshot.snapshot_id,
                },
            )
        )

    def compile_plan(
        self,
        normalized: NormalizedIntent,
        snapshot: FeasibilitySnapshot,
        decision: ConstraintDecision,
        approval: ApprovalReceipt,
    ) -> ExecutionPlanSummary:
        return ExecutionPlanSummary.model_validate(
            self._post(
                "/v1/plans/compile",
                {
                    "normalized_intent_id": normalized.normalized_intent_id,
                    "snapshot_id": snapshot.snapshot_id,
                    "decision_id": decision.decision_id,
                    "approval": approval.model_dump(mode="json"),
                },
            )
        )

    def submit_plan(self, execution_id: str, plan_hash: str, idempotency_key: str) -> SubmitReceipt:
        return SubmitReceipt.model_validate(
            self._post(
                "/v1/submissions",
                {
                    "execution_id": execution_id,
                    "plan_hash": plan_hash,
                    "idempotency_key": idempotency_key,
                },
            )
        )

    def get_submission(self, execution_id: str) -> SubmitReceipt:
        return SubmitReceipt.model_validate(self._get(f"/v1/submissions/{execution_id}"))

    def set_kill_switch(self, enabled: bool, reason: str) -> KillSwitchReceipt:
        return KillSwitchReceipt.model_validate(
            self._post("/v1/admin/kill-switch", {"enabled": enabled, "reason": reason}, admin=True)
        )

    def record_sign_only_lifecycle_event(
        self,
        record: SignOnlyLifecycleRecord,
        *,
        correlation_id: str | None = None,
    ) -> SignOnlyLifecycleRecord:
        return SignOnlyLifecycleRecord.model_validate(
            self._post(
                "/v1/sign-only/lifecycle-events",
                record.model_dump(mode="json"),
                correlation_id=correlation_id,
            )
        )

    def list_sign_only_lifecycle_events(
        self,
        execution_id: str,
        *,
        limit: int | None = None,
        before_event_id: int | None = None,
        correlation_id: str | None = None,
    ) -> list[SignOnlyLifecycleRecord]:
        payload = self._get(
            f"/v1/sign-only/lifecycle-events/{execution_id}",
            params=self._query_params(limit=limit, before_event_id=before_event_id),
            correlation_id=correlation_id,
        )
        return [SignOnlyLifecycleRecord.model_validate(item) for item in payload]

    def list_execution_lifecycle_events(
        self,
        execution_id: str,
        *,
        limit: int | None = None,
        before_event_id: int | None = None,
        correlation_id: str | None = None,
    ) -> list[ExecutionLifecycleEvent]:
        payload = self._get(
            f"/v1/lifecycle/executions/{execution_id}/events",
            params=self._query_params(limit=limit, before_event_id=before_event_id),
            correlation_id=correlation_id,
        )
        return [ExecutionLifecycleEvent.model_validate(item) for item in payload]

    def list_admin_audit_events(
        self,
        *,
        limit: int | None = None,
        before_audit_id: int | None = None,
        operation: str | None = None,
        principal_subject: str | None = None,
        result: str | None = None,
        audit_correlation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> list[AdminAuditEvent]:
        payload = self._get(
            "/v1/admin/audit-events",
            admin=True,
            params=self._query_params(
                limit=limit,
                before_audit_id=before_audit_id,
                operation=operation,
                principal_subject=principal_subject,
                result=result,
                correlation_id=audit_correlation_id,
            ),
            correlation_id=correlation_id,
        )
        return [AdminAuditEvent.model_validate(item) for item in payload]

    def cancel_order(
        self,
        account_id: str,
        order_id: str,
        reason: str,
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
    ) -> CancelReceipt:
        return CancelReceipt.model_validate(
            self._post(
                "/v1/admin/cancel-order",
                {
                    "account_id": account_id,
                    "order_id": order_id,
                    "execution_id": execution_id,
                    "reason": reason,
                },
                admin=True,
                correlation_id=correlation_id,
            )
        )

    def reconcile(
        self,
        account_id: str,
        reason: str,
        execution_id: str | None = None,
        *,
        correlation_id: str | None = None,
    ) -> ReconcileReport:
        return ReconcileReport.model_validate(
            self._post(
                "/v1/admin/reconcile",
                {"account_id": account_id, "execution_id": execution_id, "reason": reason},
                admin=True,
                correlation_id=correlation_id,
            )
        )
