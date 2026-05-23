from __future__ import annotations

from .client import ExecutorClient
from .models import (
    ApprovalReceipt,
    CanaryApprovalReference,
    CanaryEvidenceReference,
    CanaryReadinessReport,
    TradeIntent,
)


def propose_and_compile(
    client: ExecutorClient,
    intent: TradeIntent,
    approval: ApprovalReceipt,
):
    """Executor-adapter orchestration helper.

    It does not sign or submit by itself. The executor decides feasibility and
    compiles a plan summary.
    """

    normalized = client.normalize_intent(intent)
    snapshot = client.capture_snapshot(normalized)
    decision = client.evaluate_decision(normalized, snapshot)
    return client.compile_plan(normalized, snapshot, decision, approval)


def build_canary_readiness_report(
    evidence: CanaryEvidenceReference,
    *,
    approval: CanaryApprovalReference | None = None,
    blocked_reasons: list[str] | None = None,
) -> CanaryReadinessReport:
    """Build a local canary report from references only.

    Hermes does not sign, post, cancel, hold executor DB credentials, or call CLOB.
    """

    reasons = blocked_reasons or ["reviewed release decision and armed approval are absent"]
    return CanaryReadinessReport(
        status="BLOCKED",
        evidence=evidence,
        approval=approval,
        blocked_reasons=reasons,
        live_submit_allowed=False,
        remote_side_effects=False,
        secrets_included=False,
    )
