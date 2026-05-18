from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_polymarket_control.models import (
    ExecutionLifecycleEvent,
    MarketRef,
    OrderLifecycleDivergence,
    QuantityIntent,
    RedactedPayloadEnvelope,
    ReconcileOrderLocalResponse,
    Side,
    SignOnlyLifecycleRecord,
    StandardSignOnlyConstructionReceipt,
    StandardSignOnlyConstructionRequest,
    TimeInForce,
    TradeIntent,
)


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


def test_sign_only_lifecycle_record_validates_boundary():
    ok = SignOnlyLifecycleRecord(
        execution_id="exec-1",
        account_id="acct",
        state="SIGNED_DRY_RUN",
        event="SIGNED_WITHOUT_POST",
        client_event_id="evt-1",
        signed_order_ref="sign-only:redacted-ref",
        no_remote_side_effect=True,
    )
    assert ok.signed_order_ref == "sign-only:redacted-ref"

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


def test_standard_sign_only_construction_models_validate_redaction_boundary():
    digest = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    request = StandardSignOnlyConstructionRequest(
        execution_id="exec-1",
        account_id="acct",
        plan_hash="hash-1",
        signed_order_ref="sign-only:exec-1:hash-1:digest",
        signed_order_digest=digest,
        no_remote_side_effect=True,
    )
    assert request.signed_order_digest == digest

    receipt = StandardSignOnlyConstructionReceipt(
        execution_id="exec-1",
        signed_order_ref="sign-only:exec-1:hash-1:digest",
        signed_order_digest=digest,
        lifecycle_records=[
            SignOnlyLifecycleRecord(
                execution_id="exec-1",
                account_id="acct",
                state="SIGNED_DRY_RUN",
                event="SIGNED_WITHOUT_POST",
                signed_order_ref="sign-only:exec-1:hash-1:digest",
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
            plan_hash="hash-1",
            signed_order_ref="raw-signed-order",
            signed_order_digest=digest,
            no_remote_side_effect=True,
        )
    with pytest.raises(ValueError):
        StandardSignOnlyConstructionRequest(
            execution_id="exec-1",
            account_id="acct",
            plan_hash="hash-1",
            signed_order_ref="sign-only:exec-1",
            signed_order_digest="not-a-digest",
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

    with pytest.raises(ValidationError):
        OrderLifecycleDivergence(
            kind="LOCAL_REMOTE_UNKNOWN_REMOTE_MISSING",
            event="RECONCILE_MISSING",
            operator_required=False,
            no_remote_side_effect=False,
            reason="bad",
        )
