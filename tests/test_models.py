from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_polymarket_executor_adapter.models import (
    ApprovalReceipt,
    CanaryApprovalReference,
    CanaryEvidenceReference,
    CanaryReadinessReport,
    ExecutionPlanSummary,
    ExecutionLifecycleEvent,
    MarketRef,
    NormalizedIntent,
    QuantityBound,
    OrderLifecycleDivergence,
    QuantityIntent,
    RedactedPayloadEnvelope,
    ReconcileReport,
    ReconcileOrderLocalResponse,
    Side,
    SignOnlyLifecycleRecord,
    StandardSignOnlyConstructionReceipt,
    StandardSignOnlyConstructionRequest,
    TimeInForce,
    TradeIntent,
)
from hermes_polymarket_executor_adapter.tools import build_canary_readiness_report

HASH_1 = "1" * 64
DIGEST_1 = "2" * 64
SIGN_ONLY_REF_1 = f"sign-only:exec-1:{HASH_1}:{DIGEST_1}"


def test_quantity_requires_exactly_one_bound():
    with pytest.raises(ValidationError):
        QuantityIntent()
    with pytest.raises(ValidationError):
        QuantityIntent(max_notional="10", max_shares="5")
    assert QuantityIntent(max_notional="10").max_notional == "10"


def test_quantity_must_be_positive_canonical_decimal():
    for bad in ["0", "0.0", "1e-3", " 1", "1 ", ".5", "1.", "00.1"]:
        with pytest.raises(ValidationError):
            QuantityIntent(max_notional=bad)


def test_trade_intent_limit_price_bounds():
    for bad in ["0", "0.0", "1.5", "1e-3", ".5", "1."]:
        with pytest.raises(ValidationError):
            TradeIntent(
                client_intent_id="i1",
                account_id="a1",
                market=MarketRef(condition_id="c1"),
                token_id="t1",
                side=Side.BUY,
                quantity=QuantityIntent(max_notional="10"),
                limit_price=bad,
            )


def test_quantity_bound_and_normalized_intent_validate_canonical_decimals():
    with pytest.raises(ValidationError):
        QuantityBound(kind="WORST_CASE_QUOTE_NOTIONAL", amount="0")
    with pytest.raises(ValidationError):
        NormalizedIntent(
            normalized_intent_id="n1",
            intent_hash=HASH_1,
            account_id="acct",
            market=MarketRef(condition_id="c1"),
            token_id="tok",
            side=Side.BUY,
            quantity_bound=QuantityBound(kind="WORST_CASE_QUOTE_NOTIONAL", amount="10"),
            limit_price="1.5",
        )


def test_trade_intent_rejects_extra_fields():
    with pytest.raises(ValidationError):
        TradeIntent(
            client_intent_id="i1",
            account_id="a1",
            market=MarketRef(condition_id="c1"),
            token_id="t1",
            side=Side.BUY,
            quantity=QuantityIntent(max_notional="10"),
            limit_price="0.5",
            time_in_force=TimeInForce.GTC,
            signed_order="forbidden",
        )


def test_id_and_ref_fields_must_not_be_blank():
    with pytest.raises(ValidationError):
        MarketRef(condition_id=" ")
    with pytest.raises(ValidationError):
        TradeIntent(
            client_intent_id="i1",
            account_id=" ",
            market=MarketRef(condition_id="c1"),
            token_id="t1",
            side=Side.BUY,
            quantity=QuantityIntent(max_notional="10"),
            limit_price="0.5",
        )
    with pytest.raises(ValidationError):
        CanaryEvidenceReference(
            artifact_sha256="a" * 64,
            evidence_manifest_sha256="b" * 64,
            manifest_path=" ",
            release_status="source-candidate",
        )
    with pytest.raises(ValidationError):
        CanaryApprovalReference(
            approval_id="approval-1",
            approval_hash="c" * 64,
            scope="REAL_FUNDS_CANARY",
            expires_at="2099-01-01T00:00:00Z",
            operator_identity_ref=" ",
        )


def test_sign_only_lifecycle_record_validates_boundary():
    ok = SignOnlyLifecycleRecord(
        execution_id="exec-1",
        account_id="acct",
        state="SIGNED_DRY_RUN",
        event="SIGNED_WITHOUT_POST",
        client_event_id="evt-1",
        signed_order_ref=SIGN_ONLY_REF_1,
        no_remote_side_effect=True,
    )
    assert ok.signed_order_ref == SIGN_ONLY_REF_1

    import pytest
    with pytest.raises(ValueError):
        SignOnlyLifecycleRecord(
            execution_id="exec-1",
            account_id="acct",
            state="RESERVATION_PREPARED",
            event="PREPARE_RESERVATION",
            client_event_id=" ",
            signed_order_ref=None,
            no_remote_side_effect=True,
        )
    with pytest.raises(ValueError):
        SignOnlyLifecycleRecord(
            execution_id="exec-1",
            account_id="acct",
            state="RESERVATION_PREPARED",
            event="PREPARE_RESERVATION",
            signed_order_ref="forbidden-ref",
            no_remote_side_effect=True,
        )
    with pytest.raises(ValueError):
        SignOnlyLifecycleRecord(
            execution_id="exec-1",
            account_id="acct",
            state="SIGNED_DRY_RUN",
            event="SIGNED_WITHOUT_POST",
            signed_order_ref="sign-only:redacted-ref",
            no_remote_side_effect=True,
        )
    with pytest.raises(ValueError):
        SignOnlyLifecycleRecord(
            execution_id="exec-1",
            account_id="acct",
            state="SIGNED_DRY_RUN",
            event="SIGNED_WITHOUT_POST",
            signed_order_ref=f"sign-only:exec-2:{HASH_1}:{DIGEST_1}",
            no_remote_side_effect=True,
        )


def test_standard_sign_only_construction_models_validate_redaction_boundary():
    request = StandardSignOnlyConstructionRequest(
        execution_id="exec-1",
        account_id="acct",
        plan_hash=HASH_1,
        signed_order_ref=SIGN_ONLY_REF_1,
        signed_order_digest=DIGEST_1,
        no_remote_side_effect=True,
    )
    assert request.signed_order_digest == DIGEST_1

    receipt = StandardSignOnlyConstructionReceipt(
        execution_id="exec-1",
        signed_order_ref=SIGN_ONLY_REF_1,
        signed_order_digest=DIGEST_1,
        lifecycle_records=[
            SignOnlyLifecycleRecord(
                execution_id="exec-1",
                account_id="acct",
                state="SIGNED_DRY_RUN",
                event="SIGNED_WITHOUT_POST",
                signed_order_ref=SIGN_ONLY_REF_1,
                no_remote_side_effect=True,
            )
        ],
        no_remote_side_effect=True,
    )
    assert receipt.signed_order_ref.startswith("sign-only:")

    with pytest.raises(ValueError):
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash=HASH_1,
            signed_order_ref="raw-signed-order",
            signed_order_digest=DIGEST_1,
            no_remote_side_effect=True,
        )
    with pytest.raises(ValueError):
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash=HASH_1,
            signed_order_ref="sign-only:exec-1",
            signed_order_digest="not-a-digest",
            no_remote_side_effect=True,
        )


def test_standard_sign_only_construction_ref_must_bind_plan_hash():
    with pytest.raises(ValidationError):
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash="hash-1",
            signed_order_ref=SIGN_ONLY_REF_1,
            signed_order_digest=DIGEST_1,
            no_remote_side_effect=True,
        )
    with pytest.raises(ValidationError):
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash=HASH_1,
            signed_order_ref=f"sign-only:exec-1:{'3' * 64}:{DIGEST_1}",
            signed_order_digest=DIGEST_1,
            no_remote_side_effect=True,
        )


def test_execution_lifecycle_payload_requires_redacted_envelope():
    event = ExecutionLifecycleEvent(
        execution_id="exec-1",
        account_id="acct",
        event_type="CANCEL_REQUESTED_NON_LIVE",
        event_source="pmx-api",
        payload=RedactedPayloadEnvelope(
            schema_version=1,
            kind="cancel_requested_non_live",
            correlation_id="corr",
            redacted_fields=["private_key", "clob_secret"],
            body={"no_remote_side_effect": True},
        ),
    )
    assert event.payload.body["no_remote_side_effect"] is True

    with pytest.raises(ValidationError):
        RedactedPayloadEnvelope(
            schema_version=0,
            kind="bad",
            correlation_id=None,
            redacted_fields=[],
            body={},
        )
    with pytest.raises(ValidationError):
        RedactedPayloadEnvelope(
            schema_version=1,
            kind="bad",
            correlation_id=None,
            redacted_fields=[],
            body={"private_key": "secret"},
        )


def test_reconcile_order_local_response_validates_local_only_boundary():
    divergence = OrderLifecycleDivergence(
        kind="LOCAL_REMOTE_UNKNOWN_REMOTE_MISSING",
        event="RECONCILE_MISSING",
        operator_required=False,
        no_remote_side_effect=True,
        reason="first missing observation",
    )
    response = ReconcileOrderLocalResponse(
        order_id="order-1",
        divergence=divergence,
        updated_order=None,
        no_remote_side_effect=True,
    )
    assert response.divergence.event == "RECONCILE_MISSING"
    unknown = OrderLifecycleDivergence(
        kind="LOCAL_REMOTE_UNKNOWN_STILL_UNKNOWN",
        event="RECONCILE_UNKNOWN",
        operator_required=True,
        no_remote_side_effect=True,
        reason="remote truth stayed unknown",
    )
    assert unknown.event == "RECONCILE_UNKNOWN"

    with pytest.raises(ValidationError):
        OrderLifecycleDivergence(
            kind="LOCAL_REMOTE_UNKNOWN_REMOTE_MISSING",
            event="RECONCILE_MISSING",
            operator_required=False,
            no_remote_side_effect=False,
            reason="bad",
        )


def test_canary_readiness_report_is_reference_only_and_blocked():
    evidence = CanaryEvidenceReference(
        artifact_sha256="a" * 64,
        evidence_manifest_sha256="b" * 64,
        manifest_path="polymarket-execution-engine/evidence/current/manifest.json",
        release_status="shadow-ready SDK sign-only candidate",
    )
    approval = CanaryApprovalReference(
        approval_id="approval-1",
        approval_hash="c" * 64,
        scope="REAL_FUNDS_CANARY",
        expires_at="2099-01-01T00:00:00Z",
        operator_identity_ref="operator-ref",
    )
    report = build_canary_readiness_report(evidence, approval=approval)
    assert report.status == "REVIEW_PACKAGE_ONLY"
    assert report.live_submit_allowed is False
    assert report.remote_side_effects is False
    assert report.secrets_included is False
    assert report.blocked_reasons == []

    with pytest.raises(ValidationError):
        CanaryReadinessReport(
            status="DRY_RUN_READY",
            evidence=evidence,
            approval=approval,
            live_submit_allowed=True,
            remote_side_effects=False,
            secrets_included=False,
        )
    with pytest.raises(ValidationError):
        CanaryReadinessReport(
            status="DRY_RUN_READY",
            evidence=evidence,
            approval=None,
            blocked_reasons=[],
            live_submit_allowed=False,
            remote_side_effects=False,
            secrets_included=False,
        )


def test_approval_receipt_and_canary_approval_require_future_expiry():
    with pytest.raises(ValidationError):
        ApprovalReceipt(
            approval_id="approval-1",
            approved_by="operator",
            approved_at="2099-01-01T00:00:00Z",
            expires_at="2099-01-02T00:00:00Z",
            approval_scope="CONTROLLED_CANARY",
            approval_hash=HASH_1,
            bound_artifact_sha256=HASH_1,
            bound_evidence_manifest_sha256=HASH_1,
            bound_snapshot_hash=HASH_1,
            bound_decision_hash=HASH_1,
            bound_plan_hash=HASH_1,
            operator_identity_ref="operator-ref",
        )
    with pytest.raises(ValidationError):
        CanaryApprovalReference(
            approval_id="approval-1",
            approval_hash=HASH_1,
            scope="REAL_FUNDS_CANARY",
            expires_at="2000-01-01T00:00:00Z",
            operator_identity_ref="operator-ref",
        )


def test_execution_plan_summary_and_reconcile_report_enforce_bounds():
    with pytest.raises(ValidationError):
        ExecutionPlanSummary(
            execution_id="exec-1",
            account_id="acct",
            normalized_intent_id="norm-1",
            snapshot_id="snap-1",
            snapshot_hash=HASH_1,
            decision_id="dec-1",
            decision_hash=HASH_1,
            approval_id="approval-1",
            approval_hash=HASH_1,
            plan_hash=HASH_1,
            status="BLOCKED",
            condition_id="cond",
            token_id="tok",
            side=Side.BUY,
            quantity_bound=QuantityBound(kind="WORST_CASE_QUOTE_NOTIONAL", amount="10"),
            limit_price="0.5",
            time_in_force=TimeInForce.GTC,
            max_exposure="10",
            executor_version="0.28.0",
            contract_version="1.0.0-draft",
            explanation=[],
        )
    with pytest.raises(ValidationError):
        ReconcileReport(reconcile_id="r1", status="SCHEDULED", checked_orders=-1)
