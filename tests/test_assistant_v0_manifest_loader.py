from __future__ import annotations

import json

import pytest


def _write_json(path, payload):
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest():
    return {
        "name": "polymarket-trading-assistant-v0-safe-tools",
        "version": "0.1.0",
        "tools": [
            {"name": "risk_review_trade_plan", "input_schema": {"type": "object"}},
            {
                "name": "dry_run_trade_plan",
                "fixed_executor_mode": "BLOCKED_DRY_RUN",
                "allow_mode_override": False,
                "input_schema": {"type": "object"},
            },
            {"name": "get_execution_status", "input_schema": {"type": "object"}},
        ],
        "forbidden_effects": ["approve_trade_plan", "post_order", "raw_clob_request"],
    }


def _conformance():
    return {
        "contract_version": "assistant-v0",
        "target_component": "hermes-polymarket-executor-adapter",
        "safe_session_tools": [
            "create_user_thesis",
            "search_trade_expressions",
            "compare_trade_expressions",
            "draft_trade_plan",
            "record_operator_review_reference",
            "risk_review_trade_plan",
            "dry_run_trade_plan",
            "get_execution_status",
            "mark_dry_run_report_cancelled",
            "review_trade_outcome",
        ],
        "adapter_required_tools": [
            "risk_review_trade_plan",
            "dry_run_trade_plan",
            "get_execution_status",
        ],
        "forbidden_tool_names": ["approve_trade_plan", "post_order", "raw_clob_request"],
        "dry_run_executor_mode_contract": {
            "tool": "dry_run_trade_plan",
            "fixed_executor_mode": "BLOCKED_DRY_RUN",
            "allow_mode_override": False,
        },
    }


def test_manifest_loader_returns_immutable_contracts_and_diagnostics(tmp_path):
    from hermes_polymarket_executor_adapter.assistant_v0_manifest_loader import (
        load_assistant_v0_contracts,
    )

    manifest_path = tmp_path / "mcp-tool-manifest.v0.json"
    conformance_path = tmp_path / "adapter-conformance.v0.json"
    _write_json(manifest_path, _manifest())
    _write_json(conformance_path, _conformance())

    contracts = load_assistant_v0_contracts(manifest_path, conformance_path)

    assert contracts.contract_version == "assistant-v0"
    assert contracts.safe_session_tools == (
        "compare_trade_expressions",
        "create_user_thesis",
        "draft_trade_plan",
        "dry_run_trade_plan",
        "get_execution_status",
        "mark_dry_run_report_cancelled",
        "record_operator_review_reference",
        "review_trade_outcome",
        "risk_review_trade_plan",
        "search_trade_expressions",
    )
    assert contracts.adapter_required_tools == (
        "dry_run_trade_plan",
        "get_execution_status",
        "risk_review_trade_plan",
    )
    assert contracts.dry_run_fixed_executor_mode == "BLOCKED_DRY_RUN"
    assert contracts.diagnostics == {
        "adapter_required_tool_count": 3,
        "forbidden_tool_count": 3,
        "safe_tool_count": 10,
        "target_component": "hermes-polymarket-executor-adapter",
    }

    with pytest.raises(TypeError):
        contracts.safe_session_tools[0] = "mutated"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda manifest, conformance: manifest["tools"].append(
                {"name": "approve_trade_plan", "input_schema": {"type": "object"}}
            ),
            "forbidden_tool_exposed:approve_trade_plan",
        ),
        (
            lambda manifest, conformance: conformance["safe_session_tools"].append("extra_tool"),
            "safe_tool_mismatch",
        ),
        (
            lambda manifest, conformance: manifest["tools"][1].update(
                {"fixed_executor_mode": "LIVE"}
            ),
            "dry_run_fixed_mode_mismatch",
        ),
        (
            lambda manifest, conformance: conformance["dry_run_executor_mode_contract"].update(
                {"allow_mode_override": True}
            ),
            "dry_run_mode_override_allowed",
        ),
        (
            lambda manifest, conformance: conformance.update({"contract_version": ""}),
            "contract_version_mismatch",
        ),
        (
            lambda manifest, conformance: conformance.update({"target_component": ""}),
            "target_component_mismatch",
        ),
    ],
)
def test_manifest_loader_fails_closed_on_contract_drift(tmp_path, mutate, expected_code):
    from hermes_polymarket_executor_adapter.assistant_v0_manifest_loader import (
        AssistantV0ContractLoadError,
        load_assistant_v0_contracts_from_objects,
        load_assistant_v0_contracts,
    )

    manifest = _manifest()
    conformance = _conformance()
    mutate(manifest, conformance)
    manifest_path = tmp_path / "mcp-tool-manifest.v0.json"
    conformance_path = tmp_path / "adapter-conformance.v0.json"
    _write_json(manifest_path, manifest)
    _write_json(conformance_path, conformance)

    with pytest.raises(AssistantV0ContractLoadError) as raised:
        load_assistant_v0_contracts(manifest_path, conformance_path)

    assert raised.value.code == expected_code


def test_manifest_loader_supports_in_memory_objects():
    from hermes_polymarket_executor_adapter.assistant_v0_manifest_loader import (
        load_assistant_v0_contracts_from_objects,
    )

    contracts = load_assistant_v0_contracts_from_objects(_manifest(), _conformance())
    assert contracts.contract_version == "assistant-v0"
