from __future__ import annotations


class FakeContext:
    def __init__(self) -> None:
        self.tools: dict[str, dict] = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_registers_assistant_v0_facade_without_forbidden_tools():
    from hermes_polymarket_executor_adapter.assistant_v0_contracts import FORBIDDEN_TOOL_NAMES
    from hermes_polymarket_executor_adapter.assistant_v0_facade import ASSISTANT_V0_TOOLSET
    from hermes_polymarket_executor_adapter.hermes_plugin import register

    ctx = FakeContext()
    register(ctx)

    facade_tools = {
        name: meta for name, meta in ctx.tools.items() if meta["toolset"] == ASSISTANT_V0_TOOLSET
    }
    assert set(facade_tools) == {
        "risk_review_trade_plan",
        "dry_run_trade_plan",
        "get_execution_status",
    }
    assert not (FORBIDDEN_TOOL_NAMES & set(ctx.tools))
    assert all(meta["requires_env"] == [] for meta in facade_tools.values())
    assert "review reference" in facade_tools["dry_run_trade_plan"]["description"]
    assert "authorization" not in facade_tools["dry_run_trade_plan"]["description"].lower()


def test_facade_rejects_invalid_request_before_handler_dispatch():
    from hermes_polymarket_executor_adapter.assistant_v0_facade import AssistantV0Facade

    calls = []

    def handler(payload):
        calls.append(payload)
        return {"unexpected": True}

    facade = AssistantV0Facade(handlers={"dry_run_trade_plan": handler})
    result = facade.dispatch(
        "dry_run_trade_plan",
        {
            "plan_id": "plan-fixture-001",
            "review_reference_id": "review-reference-fixture-001",
            "idempotency_key": "conformance-mode-override-001",
            "mode": "LIVE",
        },
    )

    assert calls == []
    assert result["ok"] is False
    assert result["submitted_live"] is False
    assert result["executor_called"] is False
    assert result["violations"] == [
        "dry_run_trade_plan:mode_override",
        "schema_rejection:dry_run_trade_plan:unexpected_field:mode",
    ]


def test_default_dry_run_facade_response_is_blocked_and_non_live():
    from hermes_polymarket_executor_adapter.assistant_v0_contracts import DRY_RUN_FIXED_EXECUTOR_MODE
    from hermes_polymarket_executor_adapter.assistant_v0_facade import AssistantV0Facade

    result = AssistantV0Facade().dispatch(
        "dry_run_trade_plan",
        {
            "plan_id": "plan-fixture-001",
            "review_reference_id": "review-reference-fixture-001",
            "idempotency_key": "conformance-valid-dry-run-001",
        },
    )

    assert result["ok"] is False
    assert result["code"] == "STUB_NOT_BOUND"
    assert result["kind"] == "DryRunResult"
    assert result["executor_mode"] == DRY_RUN_FIXED_EXECUTOR_MODE
    assert result["payload"]["status"] == "BLOCKED"
    assert result["payload"]["submitted_live"] is False
    assert result["payload"]["validation_errors"] == [
        "assistant_v0_facade_stub_no_executor_binding"
    ]


def test_facade_marks_assistant_local_tools_as_not_adapter_executed():
    from hermes_polymarket_executor_adapter.assistant_v0_facade import AssistantV0Facade

    result = AssistantV0Facade().dispatch(
        "record_operator_review_reference",
        {
            "plan_id": "plan-fixture-001",
            "reviewed_by": "operator-fixture-001",
            "scope": "DRY_RUN_REFERENCE_ONLY",
            "expires_at": "2026-05-23T08:00:00Z",
            "review_text": "Reference only.",
        },
    )

    assert result["ok"] is False
    assert result["code"] == "LOCAL_ASSISTANT_TOOL"
    assert result["executor_called"] is False
    assert "not executable authorization" in result["message"]
