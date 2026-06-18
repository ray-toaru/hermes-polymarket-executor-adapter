from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_CANONICAL_DECIMAL_RE = re.compile(r"^(0|[1-9][0-9]*)(\.[0-9]+)?$")
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SECRET_BEARING_KEY_RE = re.compile(
    r"(private[_-]?key|api[_-]?secret|api[_-]?passphrase|clob[_-]?secret|raw[_-]?signature|raw[_-]?signed[_-]?payload)",
    re.IGNORECASE,
)
_SECRET_BEARING_VALUE_RE = re.compile(
    r"(private[_-]?key|api[_-]?secret|api[_-]?passphrase|clob[_-]?secret|raw[_-]?signature|raw[_-]?signed[_-]?payload)\s*[:=]",
    re.IGNORECASE,
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("*")
    @classmethod
    def id_ref_and_path_fields_must_not_be_blank(cls, value: Any, info: Any) -> Any:
        field_name = info.field_name or ""
        is_reference_field = (
            field_name.endswith("_id")
            or field_name.endswith("_ref")
            or field_name in {"manifest_path"}
        )
        if is_reference_field and isinstance(value, str) and not value.strip():
            raise ValueError(f"{field_name} must not be blank")
        return value


def _validate_safe_identifier(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not _SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"{field} must match [A-Za-z0-9._:-] and be at most 128 characters"
        )
    return value


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


def _validate_sha256_hex(value: str, *, field: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{field} must be a lowercase 64-character SHA-256 hex string")
    return value


def _contains_secret_bearing_keys(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if isinstance(key, str) and _SECRET_BEARING_KEY_RE.search(key):
                return True
            if _contains_secret_bearing_keys(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_secret_bearing_keys(item) for item in value)
    return False


def _contains_secret_bearing_values(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_bearing_values(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_secret_bearing_values(item) for item in value)
    if isinstance(value, str):
        return bool(_SECRET_BEARING_VALUE_RE.search(value))
    return False


def _require_timezone_aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return value


def _parse_sign_only_ref(value: str, *, field: str) -> tuple[str, str, str]:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a redacted sign-only ref")
    parts = value.split(":")
    if len(parts) != 4 or parts[0] != "sign-only":
        raise ValueError(f"{field} must have format sign-only:<execution_id>:<plan_hash>:<digest>")
    execution_id, plan_hash, digest = parts[1], parts[2], parts[3]
    if not execution_id.strip():
        raise ValueError(f"{field} execution_id must not be blank")
    _validate_sha256_hex(plan_hash, field=f"{field}.plan_hash")
    _validate_sha256_hex(digest, field=f"{field}.digest")
    return execution_id, plan_hash, digest


class MarketRef(FrozenModel):
    condition_id: str
    slug: str | None
    is_sports: bool

    @field_validator("condition_id")
    @classmethod
    def condition_id_must_be_safe_identifier(cls, value: str) -> str:
        return _validate_safe_identifier(value, field="condition_id")


class QuantityIntent(FrozenModel):
    max_notional: str | None
    max_shares: str | None

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
    time_in_force: TimeInForce
    collateral_profile_id: str | None

    @field_validator(
        "client_intent_id", "account_id", "token_id", "collateral_profile_id"
    )
    @classmethod
    def trade_identifiers_must_be_safe(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return value
        return _validate_safe_identifier(value, field=info.field_name)

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

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive_decimal_string(cls, value: str) -> str:
        return _validate_decimal_string(value, field="quantity_bound.amount", positive=True)


class NormalizedIntent(FrozenModel):
    normalized_intent_id: str
    intent_hash: str
    account_id: str
    market: MarketRef
    token_id: str
    side: Side
    quantity_bound: QuantityBound
    limit_price: str
    time_in_force: TimeInForce
    collateral_profile_id: str | None

    @field_validator("limit_price")
    @classmethod
    def normalized_limit_price_must_be_decimal_string(cls, value: str) -> str:
        value = _validate_decimal_string(value, field="limit_price", positive=True)
        if Decimal(value) > Decimal("1"):
            raise ValueError("limit_price must be in (0, 1]")
        return value


class RuntimeStateSummary(FrozenModel):
    geoblock_status: Literal["ALLOWED", "BLOCKED", "UNKNOWN", "ERROR"]
    worker_status: Literal["HEALTHY", "DEGRADED", "STALE", "UNKNOWN"]
    collateral_profile_status: Literal["RESOLVED", "DEFAULT_RESOLVED", "EXPLICIT_MISSING", "UNKNOWN"]
    kill_switch_enabled: bool
    required_capabilities: list[str]


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
    approved_at: datetime
    expires_at: datetime
    approval_scope: Literal["SHADOW", "CONTROLLED_CANARY", "LIVE_SUBMIT"]
    approval_hash: str
    bound_artifact_sha256: str
    bound_evidence_manifest_sha256: str
    bound_snapshot_hash: str
    bound_decision_hash: str
    bound_plan_hash: str | None
    operator_identity_ref: str

    @field_validator(
        "approval_hash",
        "bound_artifact_sha256",
        "bound_evidence_manifest_sha256",
        "bound_snapshot_hash",
        "bound_decision_hash",
        "bound_plan_hash",
    )
    @classmethod
    def hashes_must_be_sha256(cls, value: str | None, info: Any) -> str | None:
        if value is None:
            return value
        return _validate_sha256_hex(value, field=info.field_name)

    @model_validator(mode="after")
    def expiry_must_follow_approval_time(self) -> ApprovalReceipt:
        approved_at = _require_timezone_aware(self.approved_at, field="approved_at")
        expires_at = _require_timezone_aware(self.expires_at, field="expires_at")
        now = datetime.now(timezone.utc)
        if approved_at > now:
            raise ValueError("approved_at must not be in the future")
        if expires_at <= approved_at:
            raise ValueError("expires_at must be later than approved_at")
        if expires_at <= now:
            raise ValueError("expires_at must be in the future")
        return self


class ExecutionPlanSummary(FrozenModel):
    execution_id: str
    account_id: str
    normalized_intent_id: str
    snapshot_id: str
    snapshot_hash: str
    decision_id: str
    decision_hash: str
    approval_id: str
    approval_hash: str
    plan_hash: str
    status: Literal["READY", "BLOCKED"]
    condition_id: str
    token_id: str
    side: Side
    quantity_bound: QuantityBound
    limit_price: str
    time_in_force: TimeInForce
    collateral_profile_id: str | None
    max_exposure: str
    executor_version: str
    contract_version: str
    explanation: list[str]

    @field_validator("snapshot_hash", "decision_hash", "approval_hash", "plan_hash")
    @classmethod
    def plan_hashes_must_be_sha256(cls, value: str, info: Any) -> str:
        return _validate_sha256_hex(value, field=info.field_name)

    @field_validator("limit_price")
    @classmethod
    def execution_plan_limit_price_must_be_decimal_string(cls, value: str) -> str:
        value = _validate_decimal_string(value, field="limit_price", positive=True)
        if Decimal(value) > Decimal("1"):
            raise ValueError("limit_price must be in (0, 1]")
        return value

    @field_validator("max_exposure")
    @classmethod
    def max_exposure_must_be_positive_decimal_string(cls, value: str) -> str:
        return _validate_decimal_string(value, field="max_exposure", positive=True)

    @model_validator(mode="after")
    def plan_requires_explanation(self) -> "ExecutionPlanSummary":
        if not self.explanation:
            raise ValueError("execution plans require explanation")
        return self


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


OrderLifecycleState = Literal[
    "PLANNED",
    "SIGNED",
    "POST_REQUESTED",
    "POSTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCEL_REQUESTED",
    "CANCEL_REMOTE_ACCEPTED",
    "CANCEL_CONFIRMED",
    "REMOTE_UNKNOWN",
    "PARTIAL_REMOTE_UNKNOWN",
    "FAILED",
]

OrderEventKind = Literal[
    "SIGNED",
    "POST_REQUESTED",
    "REMOTE_POSTED",
    "REMOTE_REJECTED",
    "REMOTE_UNKNOWN",
    "PARTIAL_FILL",
    "FULL_FILL",
    "CANCEL_REQUESTED",
    "CANCEL_REMOTE_ACCEPTED",
    "CANCEL_CONFIRMED",
    "RECONCILE_OPEN",
    "RECONCILE_MISSING",
    "RECONCILE_UNKNOWN",
]

RemoteOrderObservation = Literal["OPEN", "MISSING", "UNKNOWN"]

OrderLifecycleDivergenceKind = Literal[
    "NONE",
    "LOCAL_REMOTE_UNKNOWN_REMOTE_OPEN",
    "LOCAL_REMOTE_UNKNOWN_REMOTE_MISSING",
    "LOCAL_REMOTE_UNKNOWN_STILL_UNKNOWN",
    "TERMINAL_LOCAL_REMOTE_MISMATCH",
]


class OrderLifecycleRecord(FrozenModel):
    order_id: str
    execution_id: str
    account_id: str
    condition_id: str
    token_id: str
    side: str
    lifecycle_state: OrderLifecycleState
    remote_order_id: str | None
    remote_state: str | None
    created_at: datetime | None
    updated_at: datetime | None


class OrderLifecycleDivergence(FrozenModel):
    kind: OrderLifecycleDivergenceKind
    event: OrderEventKind | None
    operator_required: bool
    no_remote_side_effect: bool
    reason: str

    @model_validator(mode="after")
    def must_not_have_remote_side_effect(self) -> "OrderLifecycleDivergence":
        if not self.no_remote_side_effect:
            raise ValueError("order lifecycle divergence must not contain remote side effects")
        return self


class ReconcileOrderLocalResponse(FrozenModel):
    order_id: str
    divergence: OrderLifecycleDivergence
    updated_order: OrderLifecycleRecord | None
    no_remote_side_effect: bool

    @model_validator(mode="after")
    def must_be_local_only(self) -> "ReconcileOrderLocalResponse":
        if not self.no_remote_side_effect:
            raise ValueError("local order reconcile response must not contain remote side effects")
        return self


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
    signed_order_ref: str | None
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
            ref_execution_id, _, _ = _parse_sign_only_ref(
                self.signed_order_ref,
                field="signed_order_ref",
            )
            if ref_execution_id != self.execution_id:
                raise ValueError("signed_order_ref execution_id must match execution_id")
        elif self.signed_order_ref is not None:
            raise ValueError("signed_order_ref is only allowed for SIGNED_DRY_RUN")
        return self


class StandardSignOnlyConstructionRequest(FrozenModel):
    execution_id: str
    account_id: str
    plan_hash: str
    signed_order_ref: str | None = None
    signed_order_digest: str | None = None
    no_remote_side_effect: bool

    @field_validator("signed_order_ref")
    @classmethod
    def signed_order_ref_must_be_redacted(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_sign_only_ref(value, field="signed_order_ref")
        return value

    @field_validator("signed_order_digest")
    @classmethod
    def digest_must_be_sha256(cls, value: str | None) -> str | None:
        if value is not None:
            return _validate_sha256_hex(value, field="signed_order_digest")
        return value

    @model_validator(mode="after")
    def must_be_local_only(self) -> "StandardSignOnlyConstructionRequest":
        if not self.no_remote_side_effect:
            raise ValueError("standard sign-only construction must not contain remote side effects")
        _validate_sha256_hex(self.plan_hash, field="plan_hash")
        if self.signed_order_ref is not None:
            ref_execution_id, ref_plan_hash, ref_digest = _parse_sign_only_ref(
                self.signed_order_ref, field="signed_order_ref"
            )
            if ref_execution_id != self.execution_id:
                raise ValueError("signed_order_ref execution_id must match execution_id")
            if ref_plan_hash != self.plan_hash:
                raise ValueError("signed_order_ref plan_hash must match plan_hash")
            if self.signed_order_digest is not None and ref_digest != self.signed_order_digest:
                raise ValueError("signed_order_ref digest must match signed_order_digest")
        return self


class StandardSignOnlyConstructionReceipt(FrozenModel):
    execution_id: str
    signed_order_ref: str
    signed_order_digest: str | None
    lifecycle_records: list[SignOnlyLifecycleRecord]
    no_remote_side_effect: bool

    @model_validator(mode="after")
    def must_be_redacted_and_local_only(self) -> "StandardSignOnlyConstructionReceipt":
        if not self.no_remote_side_effect:
            raise ValueError("standard sign-only receipt must not contain remote side effects")
        _parse_sign_only_ref(self.signed_order_ref, field="signed_order_ref")
        if self.signed_order_digest is not None:
            _, _, ref_digest = _parse_sign_only_ref(self.signed_order_ref, field="signed_order_ref")
            if ref_digest != self.signed_order_digest:
                raise ValueError("signed_order_ref digest must match signed_order_digest")
        return self


class RedactedPayloadEnvelope(FrozenModel):
    schema_version: int
    kind: str
    correlation_id: str | None
    redacted_fields: list[str]
    body: dict[str, Any]

    @model_validator(mode="after")
    def must_be_v1_or_newer(self) -> "RedactedPayloadEnvelope":
        if self.schema_version < 1:
            raise ValueError("redacted payload schema_version must be >= 1")
        if _contains_secret_bearing_keys(self.body):
            raise ValueError("redacted payload body must not contain secret-bearing keys")
        if _contains_secret_bearing_values(self.body):
            raise ValueError("redacted payload body must not contain secret-bearing values")
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


LiveReadOperation = Literal["GET_ORDER", "LIST_OPEN_ORDERS", "LIST_FILLS", "LIST_POSITIONS"]
LiveReadOutcome = Literal[
    "OBSERVED",
    "MISSING",
    "BLOCKED",
    "REMOTE_REJECTED",
    "REMOTE_UNKNOWN",
    "AUTHENTICATION_FAILED",
]
LiveReadErrorCategory = Literal[
    "REMOTE_REJECTED",
    "REMOTE_UNKNOWN",
    "AUTHENTICATION_FAILED",
    "DISABLED",
    "SIGNING_UNAVAILABLE",
]


class LiveReadEventRecord(FrozenModel):
    event_id: int | None = None
    observed_at: datetime | None = None
    account_id: str
    operation: LiveReadOperation
    outcome: LiveReadOutcome
    remote_order_id: str | None = None
    remote_state: str | None = None
    error_category: LiveReadErrorCategory | None = None
    redacted_error_summary: str | None = None
    no_trading_side_effect: bool
    redacted_fields: list[str]

    @model_validator(mode="after")
    def must_be_read_only_and_redacted(self) -> "LiveReadEventRecord":
        if not self.no_trading_side_effect:
            raise ValueError("live-read event must not have trading side effects")
        if not self.redacted_fields:
            raise ValueError("live-read event must declare redacted_fields")
        if self.redacted_error_summary is not None:
            if _contains_secret_bearing_values(self.redacted_error_summary):
                raise ValueError("redacted_error_summary must not contain secret-bearing values")
        return self


AdminCapability = Literal[
    "READ_AUDIT",
    "CANCEL_ORDER",
    "CANCEL_MARKET",
    "RECONCILE",
    "KILL_SWITCH",
]


class AdminSession(FrozenModel):
    principal_subject: str
    scopes: list[Literal["ADMIN"]]
    capabilities: list[AdminCapability]
    no_remote_side_effect: bool

    @model_validator(mode="after")
    def must_be_admin_and_read_only(self) -> "AdminSession":
        if not self.principal_subject.strip():
            raise ValueError("admin principal_subject must not be blank")
        if self.scopes != ["ADMIN"]:
            raise ValueError("admin session must contain only the ADMIN scope")
        if not self.no_remote_side_effect:
            raise ValueError("admin session probe must not have remote side effects")
        return self


class KillSwitchReceipt(FrozenModel):
    scope: str
    account_id: str | None = None
    enabled: bool
    changed_at: datetime
    effective_at: datetime
    state_version: int
    persisted: bool
    reason: str

    @field_validator("scope")
    @classmethod
    def _scope_is_supported(cls, value: str) -> str:
        if value not in {"ACCOUNT", "GLOBAL"}:
            raise ValueError("kill switch scope must be ACCOUNT or GLOBAL")
        return value

    @model_validator(mode="after")
    def _account_id_matches_scope(self) -> "KillSwitchReceipt":
        if self.scope == "ACCOUNT" and (self.account_id is None or not self.account_id.strip()):
            raise ValueError("account_id must be non-empty for ACCOUNT scope")
        if self.scope == "GLOBAL" and self.account_id is not None:
            raise ValueError("account_id must be omitted for GLOBAL scope")
        return self

    @field_validator("account_id")
    @classmethod
    def _account_id_non_empty(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("account_id must be non-empty")
        return value


class ReconcileReport(FrozenModel):
    reconcile_id: str
    status: str
    checked_orders: int
    findings: list[str]

    @field_validator("checked_orders")
    @classmethod
    def checked_orders_must_be_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("checked_orders must be non-negative")
        return value


class HealthReport(FrozenModel):
    status: str
    executor_version: str
    contract_version: str
    checks: dict[str, Any]


class CanaryEvidenceReference(FrozenModel):
    artifact_sha256: str
    evidence_manifest_sha256: str
    manifest_path: str
    release_status: str

    @field_validator("artifact_sha256", "evidence_manifest_sha256")
    @classmethod
    def hashes_must_be_sha256(cls, value: str) -> str:
        return _validate_sha256_hex(value, field="canary_evidence_hash")


class CanaryApprovalReference(FrozenModel):
    approval_id: str
    approval_hash: str
    scope: Literal["REAL_FUNDS_CANARY"]
    expires_at: datetime
    operator_identity_ref: str

    @field_validator("approval_hash")
    @classmethod
    def approval_hash_must_be_sha256(cls, value: str) -> str:
        return _validate_sha256_hex(value, field="approval_hash")

    @model_validator(mode="after")
    def expires_at_must_be_future(self) -> "CanaryApprovalReference":
        expires_at = _require_timezone_aware(self.expires_at, field="expires_at")
        if expires_at <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return self


class CanaryReadinessReport(FrozenModel):
    status: Literal["BLOCKED", "DRY_RUN_READY", "REVIEW_PACKAGE_ONLY"]
    evidence: CanaryEvidenceReference
    approval: CanaryApprovalReference | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    live_submit_allowed: bool
    remote_side_effects: bool
    secrets_included: bool

    @model_validator(mode="after")
    def must_remain_executor_adapter_only(self) -> "CanaryReadinessReport":
        if self.live_submit_allowed:
            raise ValueError("Hermes canary reports must not allow live submit")
        if self.remote_side_effects:
            raise ValueError("Hermes canary reports must not record remote side effects")
        if self.secrets_included:
            raise ValueError("Hermes canary reports must not include secrets")
        if self.status == "BLOCKED" and not self.blocked_reasons:
            raise ValueError("blocked canary reports require at least one reason")
        if self.status != "BLOCKED":
            if self.approval is None:
                raise ValueError("non-blocked canary reports require approval")
            if self.blocked_reasons:
                raise ValueError("non-blocked canary reports must not include blocked_reasons")
        return self
