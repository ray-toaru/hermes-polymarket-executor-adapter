from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CANONICAL_DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(str, Enum):
    GTC = "GTC"
    FOK = "FOK"
    GTD = "GTD"
    FAK = "FAK"


def _validate_decimal_string(value: str, *, field: str, positive: bool = False) -> str:
    if not isinstance(value, str) or not _CANONICAL_DECIMAL_RE.fullmatch(value):
        raise ValueError(f"{field} must be a canonical decimal string")
    parsed = Decimal(value)
    if positive and parsed <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return value


class MarketRef(FrozenModel):
    condition_id: str
    slug: str | None = None
    is_sports: bool = False


class QuantityIntent(FrozenModel):
    max_notional: str | None = None
    max_shares: str | None = None

    @model_validator(mode="after")
    def exactly_one_bound(self) -> "QuantityIntent":
        provided = [self.max_notional is not None, self.max_shares is not None]
        if sum(provided) != 1:
            raise ValueError("exactly one of max_notional or max_shares is required")
        return self

    @field_validator("max_notional", "max_shares")
    @classmethod
    def quantity_must_be_positive_decimal_string(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_decimal_string(value, field="quantity", positive=True)


class TradeIntent(FrozenModel):
    client_intent_id: str
    account_id: str
    market: MarketRef
    token_id: str
    side: Side
    quantity: QuantityIntent
    limit_price: str
    time_in_force: TimeInForce = TimeInForce.GTC
    collateral_profile_id: str | None = None

    @field_validator("limit_price")
    @classmethod
    def limit_price_must_be_decimal_string(cls, value: str) -> str:
        value = _validate_decimal_string(value, field="limit_price", positive=True)
        parsed = Decimal(value)
        if parsed > Decimal("1"):
            raise ValueError("limit_price must be in (0, 1]")
        return value


QuantityBoundKind = Literal[
    "WORST_CASE_QUOTE_NOTIONAL",
    "WORST_CASE_BASE_SHARES",
    "UNSUPPORTED",
]


class QuantityBound(FrozenModel):
    kind: QuantityBoundKind
    amount: str


class NormalizedIntent(FrozenModel):
    normalized_intent_id: str
    intent_hash: str
    account_id: str
    market: MarketRef
    token_id: str
    side: Side
    quantity_bound: QuantityBound
    limit_price: str
    time_in_force: TimeInForce = TimeInForce.GTC
    collateral_profile_id: str | None = None


class RuntimeStateSummary(FrozenModel):
    geoblock_status: Literal["ALLOWED", "BLOCKED", "UNKNOWN", "ERROR"]
    worker_status: Literal["HEALTHY", "DEGRADED", "STALE", "UNKNOWN"]
    collateral_profile_status: Literal["RESOLVED", "DEFAULT_RESOLVED", "EXPLICIT_MISSING", "UNKNOWN"]
    kill_switch_enabled: bool
    required_capabilities: list[str] = Field(default_factory=list)


class FeasibilitySnapshot(FrozenModel):
    snapshot_id: str
    snapshot_hash: str
    normalized_intent_id: str
    runtime_state: RuntimeStateSummary
    captured_at: datetime


class ConstraintDecision(FrozenModel):
    decision_id: str
    decision_hash: str
    status: Literal["ALLOW", "BLOCK", "CLOSE_ONLY", "DEGRADED"]
    reasons: list[str]


class ApprovalReceipt(FrozenModel):
    approval_id: str
    approved_by: str
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approval_hash: str


class ExecutionPlanSummary(FrozenModel):
    execution_id: str
    account_id: str
    normalized_intent_id: str
    snapshot_id: str
    decision_id: str
    plan_hash: str
    status: Literal["READY", "BLOCKED"]
    max_exposure: str
    explanation: list[str] = Field(default_factory=list)


class SubmitReceipt(FrozenModel):
    execution_id: str
    receipt_id: str
    status: Literal["ACCEPTED", "POSTED", "PARTIAL_REMOTE_UNKNOWN", "REMOTE_UNKNOWN", "REJECTED", "BLOCKED"]
    executor_version: str
    contract_version: str


class CancelReceipt(FrozenModel):
    cancel_id: str
    order_id: str
    state: Literal[
        "REQUESTED",
        "REMOTE_ACCEPTED",
        "CONFIRMED_CANCELED",
        "NOT_CANCELED",
        "REMOTE_UNKNOWN",
        "RECONCILE_REQUIRED",
    ]


SignOnlyLifecycleState = Literal[
    "PLANNED",
    "RESERVATION_PREPARED",
    "SIGNING_REQUESTED",
    "SIGNED_DRY_RUN",
    "FAILED",
    "ABANDONED",
]

SignOnlyLifecycleEventKind = Literal[
    "PREPARE_RESERVATION",
    "REQUEST_SIGNING",
    "SIGNED_WITHOUT_POST",
    "SIGNING_FAILED",
    "ABANDON",
]


class SignOnlyLifecycleRecord(FrozenModel):
    event_id: int | None = None
    created_at: datetime | None = None
    execution_id: str
    account_id: str
    state: SignOnlyLifecycleState
    event: SignOnlyLifecycleEventKind
    client_event_id: str | None = None
    signed_order_ref: str | None = None
    no_remote_side_effect: bool

    @field_validator("client_event_id")
    @classmethod
    def client_event_id_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("client_event_id must not be blank when provided")
        return value

    @model_validator(mode="after")
    def signed_order_ref_boundary(self) -> "SignOnlyLifecycleRecord":
        if not self.no_remote_side_effect:
            raise ValueError("sign-only lifecycle records must not contain remote side effects")
        if self.state == "SIGNED_DRY_RUN":
            if not self.signed_order_ref or not self.signed_order_ref.strip():
                raise ValueError("SIGNED_DRY_RUN requires signed_order_ref")
        elif self.signed_order_ref is not None:
            raise ValueError("signed_order_ref is only allowed for SIGNED_DRY_RUN")
        return self


class RedactedPayloadEnvelope(FrozenModel):
    schema_version: int
    kind: str
    correlation_id: str | None
    redacted_fields: list[str] = Field(default_factory=list)
    body: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def must_be_v1_or_newer(self) -> "RedactedPayloadEnvelope":
        if self.schema_version < 1:
            raise ValueError("redacted payload schema_version must be >= 1")
        return self


class ExecutionLifecycleEvent(FrozenModel):
    event_id: int | None = None
    created_at: datetime | None = None
    execution_id: str
    account_id: str
    event_type: str
    event_source: str
    payload: RedactedPayloadEnvelope


class AdminAuditEvent(FrozenModel):
    audit_id: int | None = None
    created_at: datetime | None = None
    principal_subject: str
    operation: str
    request_fingerprint: str | None
    correlation_id: str | None = None
    result: str


class KillSwitchReceipt(FrozenModel):
    enabled: bool
    changed_at: datetime
    reason: str


class ReconcileReport(FrozenModel):
    reconcile_id: str
    status: str
    checked_orders: int
    findings: list[str] = Field(default_factory=list)


class HealthReport(FrozenModel):
    status: str
    executor_version: str
    contract_version: str
    checks: dict[str, Any] = Field(default_factory=dict)
