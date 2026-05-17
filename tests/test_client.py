from __future__ import annotations

import httpx
import pytest

from hermes_polymarket_control.client import ExecutorClient
from hermes_polymarket_control.config import ExecutorConfig
from hermes_polymarket_control.models import MarketRef, QuantityIntent, Side, TradeIntent


def test_service_operation_requires_service_token():
    client = ExecutorClient(ExecutorConfig(base_url="http://example.test", service_token=""))
    with pytest.raises(PermissionError):
        client.health()
    client.close()


def test_admin_operation_requires_admin_token():
    client = ExecutorClient(ExecutorConfig(base_url="http://example.test", service_token="svc"))
    with pytest.raises(PermissionError):
        client.cancel_order("acct", "order", "test")
    client.close()


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
        if url.endswith("/kill-switch"):
            return httpx.Response(202, request=httpx.Request("POST", url), json={
                "enabled": True,
                "changed_at": "2026-05-14T00:00:00Z",
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
    client.set_kill_switch(True, "test")
    client.reconcile("acct", "test")
    client.cancel_order("acct", "o1", "test")
    assert all(h["Authorization"] == "Bearer admin" for _, _, h in captured)
    client.close()


def test_v023_lifecycle_and_audit_client_methods(monkeypatch):
    captured = []

    def fake_post(self, url, json, headers):
        captured.append(("POST", url, json, headers, None))
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

    from hermes_polymarket_control.models import SignOnlyLifecycleRecord

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
    assert captured[1][4] == {"limit": 10, "before_event_id": 9}
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
