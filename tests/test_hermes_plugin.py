from __future__ import annotations

import json
from pathlib import Path
import tomllib


class FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_pyproject_exposes_hermes_plugin_entrypoint():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        project = tomllib.load(fh)

    assert project["project"]["requires-python"] == ">=3.11"
    assert (
        project["project"]["entry-points"]["hermes_agent.plugins"]["polymarket-executor"]
        == "hermes_polymarket_executor_adapter.hermes_plugin"
    )


def test_registers_service_and_admin_tools():
    from hermes_polymarket_executor_adapter.hermes_plugin import register

    ctx = FakeContext()
    register(ctx)

    assert {
        "polymarket_executor_health",
        "polymarket_normalize_intent",
        "polymarket_capture_snapshot",
        "polymarket_evaluate_decision",
        "polymarket_compile_plan",
        "polymarket_prepare_execution_plan",
        "polymarket_get_submission",
        "polymarket_list_execution_lifecycle_events",
        "polymarket_canary_report",
        "polymarket_admin_kill_switch",
        "polymarket_admin_cancel_order",
        "polymarket_admin_reconcile",
        "polymarket_admin_list_audit_events",
    }.issubset(ctx.tools)
    assert ctx.tools["polymarket_executor_health"]["toolset"] == "polymarket_executor"
    assert ctx.tools["polymarket_admin_cancel_order"]["toolset"] == "polymarket_executor_admin"
    assert ctx.tools["polymarket_admin_cancel_order"]["requires_env"] == [
        "PM_EXEC_SERVICE_TOKEN",
        "PM_EXEC_ADMIN_TOKEN",
    ]


def test_service_availability_requires_service_token(monkeypatch):
    from hermes_polymarket_executor_adapter.hermes_handlers import check_executor_available

    monkeypatch.delenv("PM_EXEC_SERVICE_TOKEN", raising=False)
    assert check_executor_available() is False
    monkeypatch.setenv("PM_EXEC_SERVICE_TOKEN", "svc")
    assert check_executor_available() is True


def test_admin_availability_requires_service_and_admin_tokens(monkeypatch):
    from hermes_polymarket_executor_adapter.hermes_handlers import check_admin_available

    monkeypatch.setenv("PM_EXEC_SERVICE_TOKEN", "svc")
    monkeypatch.delenv("PM_EXEC_ADMIN_TOKEN", raising=False)
    assert check_admin_available() is False
    monkeypatch.setenv("PM_EXEC_ADMIN_TOKEN", "admin")
    assert check_admin_available() is True


def test_health_handler_returns_json_and_closes_client(monkeypatch):
    from hermes_polymarket_executor_adapter import hermes_handlers
    from hermes_polymarket_executor_adapter.models import HealthReport

    closed = {"value": False}

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def health(self):
            return HealthReport(
                status="READY",
                executor_version="0.27.1",
                contract_version="1.0.0-draft",
                checks={"database": "ok"},
            )

        def close(self):
            closed["value"] = True

    monkeypatch.setattr(hermes_handlers.ExecutorConfig, "from_env", classmethod(lambda cls: "cfg"))
    monkeypatch.setattr(hermes_handlers, "ExecutorClient", FakeClient)

    payload = json.loads(hermes_handlers.handle_executor_health({}))

    assert payload["status"] == "READY"
    assert payload["checks"]["database"] == "ok"
    assert closed["value"] is True


def test_admin_cancel_handler_requires_reason_and_uses_client(monkeypatch):
    from hermes_polymarket_executor_adapter import hermes_handlers
    from hermes_polymarket_executor_adapter.models import CancelReceipt

    captured = {}

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def cancel_order(self, account_id, order_id, reason, *, execution_id=None, correlation_id=None):
            captured.update(
                account_id=account_id,
                order_id=order_id,
                reason=reason,
                execution_id=execution_id,
                correlation_id=correlation_id,
            )
            return CancelReceipt(cancel_id="cancel-1", order_id=order_id, state="RECONCILE_REQUIRED")

        def close(self):
            pass

    missing_reason = json.loads(
        hermes_handlers.handle_admin_cancel_order({"account_id": "acct", "order_id": "ord"})
    )
    assert "reason is required" in missing_reason["error"]

    monkeypatch.setattr(hermes_handlers.ExecutorConfig, "from_env", classmethod(lambda cls: "cfg"))
    monkeypatch.setattr(hermes_handlers, "ExecutorClient", FakeClient)
    payload = json.loads(
        hermes_handlers.handle_admin_cancel_order(
            {
                "account_id": "acct",
                "order_id": "ord",
                "reason": "operator requested",
                "execution_id": "exec-1",
                "correlation_id": "corr-1",
            }
        )
    )

    assert payload["cancel_id"] == "cancel-1"
    assert captured == {
        "account_id": "acct",
        "order_id": "ord",
        "reason": "operator requested",
        "execution_id": "exec-1",
        "correlation_id": "corr-1",
    }


def test_prepare_execution_plan_chains_safe_executor_steps(monkeypatch):
    from hermes_polymarket_executor_adapter import hermes_handlers
    from hermes_polymarket_executor_adapter.models import (
        ConstraintDecision,
        ExecutionPlanSummary,
        FeasibilitySnapshot,
        NormalizedIntent,
        RuntimeStateSummary,
    )

    order = []

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def normalize_intent(self, intent):
            order.append(("normalize", intent.client_intent_id))
            return NormalizedIntent(
                normalized_intent_id="norm-1",
                intent_hash="intent-hash",
                account_id="acct",
                market=intent.market,
                token_id=intent.token_id,
                side=intent.side,
                quantity_bound={"kind": "WORST_CASE_QUOTE_NOTIONAL", "amount": "10"},
                limit_price=intent.limit_price,
            )

        def capture_snapshot(self, normalized):
            order.append(("snapshot", normalized.normalized_intent_id))
            return FeasibilitySnapshot(
                snapshot_id="snap-1",
                snapshot_hash="a" * 64,
                normalized_intent_id=normalized.normalized_intent_id,
                runtime_state=RuntimeStateSummary(
                    geoblock_status="ALLOWED",
                    worker_status="HEALTHY",
                    collateral_profile_status="RESOLVED",
                    kill_switch_enabled=False,
                ),
                captured_at="2026-05-23T00:00:00Z",
            )

        def evaluate_decision(self, normalized, snapshot):
            order.append(("decision", snapshot.snapshot_id))
            return ConstraintDecision(
                decision_id="dec-1",
                decision_hash="b" * 64,
                status="ALLOW",
                reasons=[],
            )

        def compile_plan(self, normalized, snapshot, decision, approval):
            order.append(("compile", approval.approval_id))
            return ExecutionPlanSummary(
                execution_id="exec-1",
                account_id="acct",
                normalized_intent_id=normalized.normalized_intent_id,
                snapshot_id=snapshot.snapshot_id,
                snapshot_hash=snapshot.snapshot_hash,
                decision_id=decision.decision_id,
                decision_hash=decision.decision_hash,
                approval_id=approval.approval_id,
                approval_hash=approval.approval_hash,
                plan_hash=approval.bound_plan_hash,
                status="READY",
                condition_id="cond",
                token_id="tok",
                side="BUY",
                quantity_bound={"kind": "WORST_CASE_QUOTE_NOTIONAL", "amount": "10"},
                limit_price="0.5",
                time_in_force="GTC",
                max_exposure="10",
                executor_version="0.27.1",
                contract_version="1.0.0-draft",
            )

        def close(self):
            pass

    monkeypatch.setattr(hermes_handlers.ExecutorConfig, "from_env", classmethod(lambda cls: "cfg"))
    monkeypatch.setattr(hermes_handlers, "ExecutorClient", FakeClient)

    payload = json.loads(
        hermes_handlers.handle_prepare_execution_plan(
            {
                "intent": {
                    "client_intent_id": "intent-1",
                    "account_id": "acct",
                    "market": {"condition_id": "cond"},
                    "token_id": "tok",
                    "side": "BUY",
                    "quantity": {"max_notional": "10"},
                    "limit_price": "0.5",
                },
                "approval": {
                    "approval_id": "approval-1",
                    "approved_by": "operator",
                    "approved_at": "2026-05-23T00:00:00Z",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "approval_scope": "CONTROLLED_CANARY",
                    "approval_hash": "c" * 64,
                    "bound_artifact_sha256": "d" * 64,
                    "bound_evidence_manifest_sha256": "e" * 64,
                    "bound_snapshot_hash": "a" * 64,
                    "bound_decision_hash": "b" * 64,
                    "bound_plan_hash": "f" * 64,
                    "operator_identity_ref": "operator-ref",
                },
            }
        )
    )

    assert payload["execution_id"] == "exec-1"
    assert order == [
        ("normalize", "intent-1"),
        ("snapshot", "norm-1"),
        ("decision", "snap-1"),
        ("compile", "approval-1"),
    ]


def test_canary_report_handler_is_reference_only():
    from hermes_polymarket_executor_adapter.hermes_handlers import handle_canary_report

    payload = json.loads(
        handle_canary_report(
            {
                "evidence": {
                    "artifact_sha256": "a" * 64,
                    "evidence_manifest_sha256": "b" * 64,
                    "manifest_path": "polymarket-execution-engine/evidence/current/manifest.json",
                    "release_status": "shadow-ready SDK sign-only candidate",
                },
                "blocked_reasons": ["release decision is not reviewed"],
            }
        )
    )

    assert payload["status"] == "BLOCKED"
    assert payload["live_submit_allowed"] is False
    assert payload["remote_side_effects"] is False
    assert payload["secrets_included"] is False
