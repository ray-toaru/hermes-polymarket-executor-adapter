from __future__ import annotations

import httpx
import pytest

from hermes_polymarket_executor_adapter.client import ExecutorClient, ExecutorHttpError
from hermes_polymarket_executor_adapter.config import ExecutorConfig
from hermes_polymarket_executor_adapter.models import (
    MarketRef,
    QuantityIntent,
    Side,
    StandardSignOnlyConstructionRequest,
    TradeIntent,
)

HASH_1 = "1" * 64
DIGEST_1 = "2" * 64
SIGN_ONLY_REF_1 = f"sign-only:exec-1:{HASH_1}:{DIGEST_1}"


def test_service_operation_requires_service_token():
    client = ExecutorClient(ExecutorConfig(base_url="http://example.test", service_token=""))
    with pytest.raises(PermissionError):
        client.health()
    client.close()


def test_executor_config_rejects_relative_base_url():
    with pytest.raises(ValueError):
        ExecutorConfig(base_url="/relative", service_token="svc")


def test_get_paths_url_encode_identifiers(monkeypatch):
    captured = {}

    def fake_get(self, url, headers):
        captured["url"] = url
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "execution_id": "exec/with space",
            "receipt_id": "receipt-1",
            "status": "BLOCKED",
            "executor_version": "0.28.0",
            "contract_version": "1.0.0-draft",
        })

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor/", service_token="svc"))
    client.get_submission("exec/with space")
    assert captured["url"] == "http://executor/v1/submissions/exec%2Fwith%20space"
    client.close()


def test_executor_error_preserves_envelope(monkeypatch):
    def fake_get(self, url, headers):
        return httpx.Response(409, request=httpx.Request("GET", url), json={
            "code": "conflict",
            "message": "plan hash mismatch",
            "correlation_id": "corr-err",
        })

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    with pytest.raises(ExecutorHttpError) as raised:
        client.health()
    assert raised.value.status_code == 409
    assert raised.value.code == "conflict"
    assert raised.value.correlation_id == "corr-err"
    assert "plan hash mismatch" in str(raised.value)
    client.close()


def test_admin_operation_requires_admin_token():
    client = ExecutorClient(ExecutorConfig(base_url="http://example.test", service_token="svc"))
    with pytest.raises(PermissionError):
        client.cancel_order("acct", "order", "test")
    client.close()


def test_submit_plan_posts_explicit_mode(monkeypatch):
    captured = {}

    def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(202, request=httpx.Request("POST", url), json={
            "execution_id": json["execution_id"],
            "receipt_id": "receipt-1",
            "status": "BLOCKED",
            "executor_version": "0.28.0",
            "contract_version": "1.0.0-draft",
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    receipt = client.submit_plan("exec-1", "a" * 64, "idem-1")
    assert receipt.status == "BLOCKED"
    assert captured["url"] == "http://executor/v1/submissions"
    assert captured["json"]["mode"] == "BLOCKED_DRY_RUN"
    client.close()


def test_submit_plan_forwards_correlation_id_header(monkeypatch):
    captured = {}

    def fake_post(self, url, json, headers):
        captured["headers"] = headers
        return httpx.Response(202, request=httpx.Request("POST", url), json={
            "execution_id": json["execution_id"],
            "receipt_id": "receipt-1",
            "status": "BLOCKED",
            "executor_version": "0.28.0",
            "contract_version": "1.0.0-draft",
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    client.submit_plan("exec-1", "a" * 64, "idem-1", correlation_id="corr-submit-1")
    assert captured["headers"]["X-Correlation-Id"] == "corr-submit-1"
    client.close()


def test_submit_plan_rejects_live_mode():
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    with pytest.raises(ValueError, match="BLOCKED_DRY_RUN"):
        client.submit_plan("exec-1", "a" * 64, "idem-1", mode="LIVE")  # type: ignore[arg-type]
    client.close()


def test_executor_config_from_env_requires_service_url(monkeypatch):
    monkeypatch.delenv("PM_EXEC_SERVICE_URL", raising=False)
    monkeypatch.setenv("PM_EXEC_SERVICE_TOKEN", "svc")
    with pytest.raises(RuntimeError, match="PM_EXEC_SERVICE_URL is required"):
        ExecutorConfig.from_env()


def test_normalize_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "normalized_intent_id": "n1",
            "intent_hash": "h1",
            "account_id": "acct",
            "market": {"condition_id": "cond", "slug": None, "is_sports": False},
            "token_id": "tok",
            "side": "BUY",
            "quantity_bound": {"kind": "WORST_CASE_QUOTE_NOTIONAL", "amount": "10"},
            "limit_price": "0.5",
            "time_in_force": "GTC",
            "collateral_profile_id": None,
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    intent = TradeIntent(
        client_intent_id="i1",
        account_id="acct",
        market=MarketRef(condition_id="cond"),
        token_id="tok",
        side=Side.BUY,
        quantity=QuantityIntent(max_notional="10"),
        limit_price="0.5",
    )
    normalized = client.normalize_intent(intent)
    assert normalized.normalized_intent_id == "n1"
    assert normalized.quantity_bound.kind == "WORST_CASE_QUOTE_NOTIONAL"
    assert captured["url"] == "http://executor/v1/intents/normalize"
    assert captured["headers"]["Authorization"] == "Bearer svc"
    assert "signed_order" not in captured["json"]
    assert "client_metadata" not in captured["json"]
    client.close()


def test_health_gets_expected_endpoint(monkeypatch):
    captured = {}

    def fake_get(self, url, headers):
        captured["url"] = url
        captured["headers"] = headers
        return httpx.Response(200, request=httpx.Request("GET", url), json={
            "status": "NOT_READY",
            "executor_version": "0.3.0",
            "contract_version": "1.0.0-draft",
            "checks": {"database": "not_configured"},
        })

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc"))
    report = client.health()
    assert report.status == "NOT_READY"
    assert captured["url"] == "http://executor/v1/health"
    client.close()


def test_admin_methods_use_admin_token(monkeypatch):
    captured = []

    def fake_post(self, url, json, headers):
        captured.append((url, json, headers))
        if url.endswith("/reconcile-order-local"):
            return httpx.Response(202, request=httpx.Request("POST", url), json={
                "order_id": "o1",
                "divergence": {
                    "kind": "LOCAL_REMOTE_UNKNOWN_REMOTE_MISSING",
                    "event": "RECONCILE_MISSING",
                    "operator_required": False,
                    "no_remote_side_effect": True,
                    "reason": "first missing observation",
                },
                "updated_order": None,
                "no_remote_side_effect": True,
            })
        if url.endswith("/kill-switch"):
            scope = json["scope"]
            return httpx.Response(202, request=httpx.Request("POST", url), json={
                "scope": scope,
                **({"account_id": json["account_id"]} if scope == "ACCOUNT" else {}),
                "enabled": True,
                "changed_at": "2026-05-14T00:00:00Z",
                "effective_at": "2026-05-14T00:00:00Z",
                "state_version": 1,
                "persisted": True,
                "reason": "test",
            })
        if url.endswith("/reconcile"):
            return httpx.Response(202, request=httpx.Request("POST", url), json={
                "reconcile_id": "r1",
                "status": "SCHEDULED_SCAFFOLD_ONLY",
                "checked_orders": 0,
                "findings": [],
            })
        return httpx.Response(202, request=httpx.Request("POST", url), json={
            "cancel_id": "c1",
            "order_id": "o1",
            "state": "RECONCILE_REQUIRED",
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc", admin_token="admin"))
    client.set_kill_switch("acct", True, "test")
    client.set_kill_switch(None, True, "test", scope="GLOBAL")
    client.reconcile("acct", "test")
    client.reconcile_order_local("acct", "o1", "MISSING", "first missing observation")
    client.cancel_order("acct", "o1", "test")
    assert all(h["Authorization"] == "Bearer admin" for _, _, h in captured)
    client.close()


def test_v023_lifecycle_and_audit_client_methods(monkeypatch):
    captured = []

    def fake_post(self, url, json, headers):
        captured.append(("POST", url, json, headers, None))
        if url.endswith("/v1/sign-only/standard-constructions"):
            return httpx.Response(202, request=httpx.Request("POST", url), json={
                "execution_id": json["execution_id"],
                "signed_order_ref": json["signed_order_ref"],
                "signed_order_digest": json["signed_order_digest"],
                "lifecycle_records": [{
                    "event_id": 8,
                    "created_at": "2026-05-16T00:00:00Z",
                    "execution_id": json["execution_id"],
                    "account_id": json["account_id"],
                    "state": "SIGNED_DRY_RUN",
                    "event": "SIGNED_WITHOUT_POST",
                    "client_event_id": f"sdk-standard:{HASH_1}:signed-without-post",
                    "signed_order_ref": json["signed_order_ref"],
                    "no_remote_side_effect": True,
                }],
                "no_remote_side_effect": True,
            })
        return httpx.Response(202, request=httpx.Request("POST", url), json={
            "event_id": 7,
            "created_at": "2026-05-16T00:00:00Z",
            "execution_id": "exec-1",
            "account_id": "acct",
            "state": "RESERVATION_PREPARED",
            "event": "PREPARE_RESERVATION",
            "client_event_id": "evt-1",
            "signed_order_ref": None,
            "no_remote_side_effect": True,
        })

    def fake_get(self, url, headers, params=None):
        captured.append(("GET", url, None, headers, params))
        if url.endswith("/v1/admin/audit-events"):
            return httpx.Response(200, request=httpx.Request("GET", url), json=[{
                "audit_id": 3,
                "created_at": "2026-05-16T00:00:01Z",
                "principal_subject": "admin-token",
                "operation": "CancelOrder",
                "request_fingerprint": "abc",
                "correlation_id": "corr-admin",
                "result": "ACCEPTED state=ReconcileRequired",
            }])
        if "/v1/lifecycle/executions/" in url:
            return httpx.Response(200, request=httpx.Request("GET", url), json=[{
                "event_id": 4,
                "created_at": "2026-05-16T00:00:02Z",
                "execution_id": "exec-1",
                "account_id": "acct",
                "event_type": "CANCEL_REQUESTED_NON_LIVE",
                "event_source": "pmx-api",
                "payload": {
                    "schema_version": 1,
                    "kind": "cancel_requested_non_live",
                    "correlation_id": "corr-event",
                    "redacted_fields": ["private_key", "clob_secret"],
                    "body": {"no_remote_side_effect": True},
                },
            }])
        return httpx.Response(200, request=httpx.Request("GET", url), json=[{
            "event_id": 7,
            "created_at": "2026-05-16T00:00:00Z",
            "execution_id": "exec-1",
            "account_id": "acct",
            "state": "RESERVATION_PREPARED",
            "event": "PREPARE_RESERVATION",
            "client_event_id": "evt-1",
            "signed_order_ref": None,
            "no_remote_side_effect": True,
        }])

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc", admin_token="admin"))

    from hermes_polymarket_executor_adapter.models import SignOnlyLifecycleRecord

    record = SignOnlyLifecycleRecord(
        execution_id="exec-1",
        account_id="acct",
        state="RESERVATION_PREPARED",
        event="PREPARE_RESERVATION",
        client_event_id="evt-1",
        signed_order_ref=None,
        no_remote_side_effect=True,
    )
    recorded = client.record_sign_only_lifecycle_event(record, correlation_id="corr-1")
    construction = client.record_standard_sign_only_construction(
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash=HASH_1,
            signed_order_ref=SIGN_ONLY_REF_1,
            signed_order_digest=DIGEST_1,
            no_remote_side_effect=True,
        ),
        correlation_id="corr-std",
    )
    sign_only = client.list_sign_only_lifecycle_events("exec-1", limit=10, before_event_id=9)
    lifecycle = client.list_execution_lifecycle_events("exec-1", limit=10)
    audit = client.list_admin_audit_events(
        limit=5,
        operation="CancelOrder",
        principal_subject="admin-token",
        result="ACCEPTED state=ReconcileRequired",
        audit_correlation_id="corr-admin",
        correlation_id="corr-admin-request",
    )

    assert recorded.event_id == 7
    assert construction.lifecycle_records[0].state == "SIGNED_DRY_RUN"
    assert sign_only[0].client_event_id == "evt-1"
    assert lifecycle[0].payload.schema_version == 1
    assert lifecycle[0].payload.body["no_remote_side_effect"] is True
    assert audit[0].operation == "CancelOrder"
    assert audit[0].correlation_id == "corr-admin"
    assert captured[0][3]["X-Correlation-Id"] == "corr-1"
    assert captured[-1][3]["Authorization"] == "Bearer admin"
    assert captured[-1][3]["X-Correlation-Id"] == "corr-admin-request"
    assert captured[-1][4]["correlation_id"] == "corr-admin"
    assert captured[-1][4]["principal_subject"] == "admin-token"
    assert captured[1][1].endswith("/v1/sign-only/standard-constructions")
    assert captured[1][3]["X-Correlation-Id"] == "corr-std"
    assert captured[2][4] == {"limit": 10, "before_event_id": 9}
    client.close()


def test_cancel_order_can_link_execution_id(monkeypatch):
    captured = {}

    def fake_post(self, url, json, headers):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return httpx.Response(202, request=httpx.Request("POST", url), json={
            "cancel_id": "c1",
            "order_id": "o1",
            "state": "RECONCILE_REQUIRED",
        })

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    client = ExecutorClient(ExecutorConfig(base_url="http://executor", service_token="svc", admin_token="admin"))
    receipt = client.cancel_order("acct", "o1", "operator-requested", execution_id="exec-1", correlation_id="corr-cancel")
    assert receipt.cancel_id == "c1"
    assert captured["json"]["execution_id"] == "exec-1"
    assert captured["headers"]["X-Correlation-Id"] == "corr-cancel"
    client.close()
