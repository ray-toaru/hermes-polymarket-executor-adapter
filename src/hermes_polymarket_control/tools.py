from __future__ import annotations

from .client import ExecutorClient
from .models import ApprovalReceipt, TradeIntent


def propose_and_compile(
    client: ExecutorClient,
    intent: TradeIntent,
    approval: ApprovalReceipt,
):
    """Control-plane orchestration helper.

    It does not sign or submit by itself. The executor decides feasibility and compiles a plan summary.
    """

    normalized = client.normalize_intent(intent)
    snapshot = client.capture_snapshot(normalized)
    decision = client.evaluate_decision(normalized, snapshot)
    return client.compile_plan(normalized, snapshot, decision, approval)
