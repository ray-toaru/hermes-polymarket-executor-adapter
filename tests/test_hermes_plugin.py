from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib
from types import SimpleNamespace


class FakeContext:
    def __init__(self, assistant_v0_handlers=None) -> None:
        self.tools: dict[str, dict] = {}
        self.assistant_v0_handlers = assistant_v0_handlers

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_pyproject_exposes_hermes_plugin_entrypoint():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as fh:
        project = tomllib.load(fh)

    assert project["project"]["requires-python"] == ">=3.11"
    assert project["project"]["dependencies"] == [
        "httpx==0.28.1",
        "pydantic==2.13.4",
    ]
    assert project["project"]["optional-dependencies"]["test"] == ["pytest==9.0.3"]
    assert (
        project["project"]["entry-points"]["hermes_agent.plugins"]["polymarket-executor"]
        == "hermes_polymarket_executor_adapter.hermes_plugin"
    )
    assert (
        project["project"]["scripts"]["pmx-executor-adapter"]
        == "hermes_polymarket_executor_adapter.cli:main"
    )


def test_pyproject_dependency_pins_align_with_ci_constraints():
    adapter_root = Path(__file__).resolve().parents[1]
    with (adapter_root / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    constraints: dict[str, str] = {}
    for line in (adapter_root / "constraints-ci.txt").read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, version = stripped.split("==", 1)
        constraints[name.lower().replace("_", "-")] = version

    pinned_specs = (
        list(pyproject["project"]["dependencies"])
        + list(pyproject["project"]["optional-dependencies"]["test"])
    )
    assert pinned_specs
    for spec in pinned_specs:
        assert "==" in spec
        assert ">=" not in spec
        name, version = spec.split("==", 1)
        normalized = name.lower().replace("_", "-")
        assert constraints.get(normalized) == version


def test_registers_service_and_admin_tools():
    from hermes_polymarket_executor_adapter.hermes_plugin import register

    ctx = FakeContext()
    register(ctx)

    expected_executor = {
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
    }
    actual_executor = {
        name
        for name, meta in ctx.tools.items()
        if meta["toolset"] in {"polymarket_executor", "polymarket_executor_admin"}
    }
    assert actual_executor == expected_executor
    assert ctx.tools["polymarket_executor_health"]["toolset"] == "polymarket_executor"
    assert ctx.tools["polymarket_admin_cancel_order"]["toolset"] == "polymarket_executor_admin"
    assert ctx.tools["polymarket_admin_cancel_order"]["requires_env"] == [
        "PM_EXEC_SERVICE_TOKEN",
        "PM_EXEC_ADMIN_TOKEN",
    ]
    forbidden = {"submit_plan", "post_order", "cancel_live_order", "approve_trade_plan"}
    assert not (forbidden & set(ctx.tools))
    assert "polymarket_prepare_execution_plan" in ctx.tools
    assert "polymarket_submit_plan" not in ctx.tools


def test_register_uses_injected_assistant_v0_handlers():
    from hermes_polymarket_executor_adapter.hermes_plugin import register

    calls = []

    def dry_run_handler(payload):
        calls.append(payload)
        return {
            "ok": True,
            "tool_name": "dry_run_trade_plan",
            "kind": "DryRunResult",
            "executor_called": True,
            "submitted_live": False,
            "payload": {"status": "READY"},
        }

    ctx = FakeContext(assistant_v0_handlers={"dry_run_trade_plan": dry_run_handler})
    register(ctx)
    payload = json.loads(
        ctx.tools["dry_run_trade_plan"]["handler"](
            {
                "plan_id": "plan-fixture-001",
                "review_reference_id": "review-reference-fixture-001",
                "idempotency_key": "dry-run-fixture-001",
            }
        )
    )

    assert calls == [
        {
            "plan_id": "plan-fixture-001",
            "review_reference_id": "review-reference-fixture-001",
            "idempotency_key": "dry-run-fixture-001",
        }
    ]
    assert payload["executor_called"] is True
    assert payload["payload"]["status"] == "READY"


def test_register_builds_assistant_v0_specs_via_contract_loader(monkeypatch):
    from hermes_polymarket_executor_adapter import hermes_plugin

    calls = []

    def fake_build(handlers=None):
        calls.append(handlers)
        return ()

    monkeypatch.setattr(hermes_plugin.assistant_v0_facade, "build_assistant_v0_tool_specs", fake_build)

    ctx = FakeContext()
    hermes_plugin.register(ctx)

    assert calls == [None]


def test_register_integrates_with_real_hermes_plugin_context():
    adapter_root = Path(__file__).resolve().parents[1]
    rust_root = adapter_root.parents[1]
    hermes_agent_root = rust_root / "hermes-agent"
    if not hermes_agent_root.exists():
        raise AssertionError(f"missing sibling hermes-agent checkout: {hermes_agent_root}")

    sys.path.insert(0, str(hermes_agent_root))
    try:
        from hermes_cli.plugins import PluginContext, PluginManifest
        from tools.registry import registry
    finally:
        sys.path.pop(0)

    from hermes_polymarket_executor_adapter.hermes_plugin import register

    manifest = PluginManifest(name="polymarket-executor", source="entrypoint", key="polymarket-executor")
    manager = SimpleNamespace(_plugin_tool_names=set())
    ctx = PluginContext(manifest, manager)
    before_tools = set(manager._plugin_tool_names)
    runtime_registered: set[str] = set()
    try:
        register(ctx)
        runtime_registered = set(manager._plugin_tool_names) - before_tools
        assert runtime_registered
        assert "polymarket_executor_health" in runtime_registered
        assert "polymarket_admin_cancel_order" in runtime_registered
        assert "dry_run_trade_plan" in runtime_registered
        assert "polymarket_submit_plan" not in runtime_registered
        assert "polymarket_executor_health" in registry.get_tool_names_for_toolset(
            "polymarket_executor"
        )
        assert "polymarket_admin_cancel_order" in registry.get_tool_names_for_toolset(
            "polymarket_executor_admin"
        )
    finally:
        for name in runtime_registered:
            registry.deregister(name)


def test_register_uses_injected_handlers_with_real_hermes_plugin_context():
    adapter_root = Path(__file__).resolve().parents[1]
    rust_root = adapter_root.parents[1]
    hermes_agent_root = rust_root / "hermes-agent"
    if not hermes_agent_root.exists():
        raise AssertionError(f"missing sibling hermes-agent checkout: {hermes_agent_root}")

    sys.path.insert(0, str(hermes_agent_root))
    try:
        from hermes_cli.plugins import PluginContext, PluginManifest
        from tools.registry import registry
    finally:
        sys.path.pop(0)

    from hermes_polymarket_executor_adapter.hermes_plugin import register

    calls = []

    def dry_run_handler(payload):
        calls.append(payload)
        return {
            "ok": True,
            "tool_name": "dry_run_trade_plan",
            "kind": "DryRunResult",
            "executor_called": True,
            "submitted_live": False,
            "payload": {"status": "READY"},
        }

    manifest = PluginManifest(name="polymarket-executor", source="entrypoint", key="polymarket-executor")
    manager = SimpleNamespace(_plugin_tool_names=set())
    ctx = PluginContext(manifest, manager)
    ctx.assistant_v0_handlers = {"dry_run_trade_plan": dry_run_handler}
    before_tools = set(manager._plugin_tool_names)
    runtime_registered: set[str] = set()
    try:
        register(ctx)
        runtime_registered = set(manager._plugin_tool_names) - before_tools
        payload = json.loads(
            registry.get_entry("dry_run_trade_plan").handler(
                {
                    "plan_id": "plan-fixture-001",
                    "review_reference_id": "review-reference-fixture-001",
                    "idempotency_key": "dry-run-fixture-001",
                }
            )
        )
        assert calls == [
            {
                "plan_id": "plan-fixture-001",
                "review_reference_id": "review-reference-fixture-001",
                "idempotency_key": "dry-run-fixture-001",
            }
        ]
        assert payload["executor_called"] is True
        assert payload["payload"]["status"] == "READY"
    finally:
        for name in runtime_registered:
            registry.deregister(name)


def test_component_compatibility_doc_records_executor_contract():
    compatibility_path = Path(__file__).resolve().parents[1] / "docs" / "COMPONENT_COMPATIBILITY.md"
    text = compatibility_path.read_text(encoding="utf-8")

    assert "Executor HTTP contract" in text
    assert "`executor.v1`" in text
    assert "`assistant-v0`" in text
    assert "`polymarket-executor`" in text


def test_plugin_docs_reference_integration_root_script_location():
    docs_root = Path(__file__).resolve().parents[1] / "docs"
    hermes_plugin = (docs_root / "HERMES_PLUGIN.md").read_text(encoding="utf-8")
    roadmap = (docs_root / "ROADMAP.md").read_text(encoding="utf-8")

    assert "cd /path/to/polymarket-execution-suite" in hermes_plugin
    assert "cd /path/to/polymarket-execution-suite" in roadmap
    assert "python scripts/check_hermes_profile_plugin.py" in hermes_plugin


def test_adapter_repo_includes_profile_check_wrapper_script():
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_hermes_profile_plugin.py"
    text = script.read_text(encoding="utf-8")
    assert 'runpy.run_path' in text
    assert 'check_hermes_profile_plugin.py' in text
    assert 'parents[2]' in text


def test_adapter_repo_has_no_stale_executor_version_fixtures():
    repo_root = Path(__file__).resolve().parents[1]
    stale_versions = {f"0.{minor}.{patch}" for minor, patch in ((26, 1), (27, 3))}
    this_file = Path(__file__).resolve()
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == this_file:
            continue
        if path.suffix not in {".py", ".md", ".toml", ".yaml", ".yml", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for version in stale_versions:
            assert version not in text, f"stale version {version} found in {path.relative_to(repo_root)}"


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
                executor_version="0.28.0",
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
                time_in_force=intent.time_in_force,
                collateral_profile_id=intent.collateral_profile_id,
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
                    required_capabilities=[],
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
                    collateral_profile_id=None,
                    max_exposure="10",
                    explanation=["fixture ready plan"],
                    executor_version="0.28.0",
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
                        "market": {"condition_id": "cond", "slug": None, "is_sports": False},
                        "token_id": "tok",
                        "side": "BUY",
                        "quantity": {"max_notional": "10", "max_shares": None},
                        "limit_price": "0.5",
                        "time_in_force": "GTC",
                        "collateral_profile_id": None,
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
                "approval": {
                    "approval_id": "approval-1",
                    "approval_hash": "c" * 64,
                    "scope": "REAL_FUNDS_CANARY",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "operator_identity_ref": "operator-ref",
                },
            }
        )
    )

    assert payload["status"] == "REVIEW_PACKAGE_ONLY"
    assert payload["live_submit_allowed"] is False
    assert payload["remote_side_effects"] is False
    assert payload["secrets_included"] is False


def test_health_handler_redacts_raw_executor_http_error(monkeypatch):
    from hermes_polymarket_executor_adapter import hermes_handlers
    from hermes_polymarket_executor_adapter.client import ExecutorHttpError

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def health(self):
            raise ExecutorHttpError(
                status_code=409,
                code="conflict",
                correlation_id="corr-err",
                message="executor request failed with status 409 code=conflict correlation_id=corr-err",
            )

        def close(self):
            pass

    monkeypatch.setattr(hermes_handlers.ExecutorConfig, "from_env", classmethod(lambda cls: "cfg"))
    monkeypatch.setattr(hermes_handlers, "ExecutorClient", FakeClient)

    payload = json.loads(hermes_handlers.handle_executor_health({}))
    assert payload["status_code"] == 409
    assert payload["code"] == "conflict"
    assert payload["correlation_id"] == "corr-err"
    assert "plan hash mismatch" not in payload["error"]
