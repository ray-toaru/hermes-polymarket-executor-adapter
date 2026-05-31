from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assistant_v0_contracts import DRY_RUN_FIXED_EXECUTOR_MODE, SAFE_SESSION_TOOLS


ASSISTANT_V0_CONTRACT_VERSION = "assistant-v0"
ASSISTANT_V0_TARGET_COMPONENT = "hermes-polymarket-executor-adapter"


class AssistantV0ContractLoadError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class AssistantV0Contracts:
    contract_version: str
    safe_session_tools: tuple[str, ...]
    adapter_required_tools: tuple[str, ...]
    dry_run_fixed_executor_mode: str
    diagnostics: dict[str, Any]


def load_assistant_v0_contracts(
    manifest_path: Path,
    conformance_path: Path,
) -> AssistantV0Contracts:
    manifest = _load_json_object(manifest_path)
    conformance = _load_json_object(conformance_path)

    manifest_tools = _manifest_tool_names(manifest)
    forbidden = _string_tuple(conformance.get("forbidden_tool_names"))
    for tool_name in sorted(set(manifest_tools) & set(forbidden)):
        raise AssistantV0ContractLoadError(f"forbidden_tool_exposed:{tool_name}")

    safe_session_tools = _sorted_tuple(conformance.get("safe_session_tools"))
    adapter_required_tools = _sorted_tuple(conformance.get("adapter_required_tools"))
    if safe_session_tools != tuple(sorted(SAFE_SESSION_TOOLS)):
        raise AssistantV0ContractLoadError("safe_tool_mismatch")
    if manifest_tools != adapter_required_tools:
        raise AssistantV0ContractLoadError("adapter_required_tool_mismatch")
    if not set(adapter_required_tools).issubset(set(safe_session_tools)):
        raise AssistantV0ContractLoadError("adapter_required_tool_mismatch")
    contract_version = conformance.get("contract_version")
    if contract_version != ASSISTANT_V0_CONTRACT_VERSION:
        raise AssistantV0ContractLoadError("contract_version_mismatch")
    target_component = conformance.get("target_component")
    if target_component != ASSISTANT_V0_TARGET_COMPONENT:
        raise AssistantV0ContractLoadError("target_component_mismatch")

    dry_run_tool = _tool_by_name(manifest, "dry_run_trade_plan")
    mode_contract = conformance.get("dry_run_executor_mode_contract")
    if not isinstance(mode_contract, dict):
        raise AssistantV0ContractLoadError("dry_run_contract_missing")
    fixed_mode = mode_contract.get("fixed_executor_mode")
    if dry_run_tool.get("fixed_executor_mode") != DRY_RUN_FIXED_EXECUTOR_MODE:
        raise AssistantV0ContractLoadError("dry_run_fixed_mode_mismatch")
    if fixed_mode != DRY_RUN_FIXED_EXECUTOR_MODE:
        raise AssistantV0ContractLoadError("dry_run_fixed_mode_mismatch")
    if dry_run_tool.get("allow_mode_override") is not False:
        raise AssistantV0ContractLoadError("dry_run_mode_override_allowed")
    if mode_contract.get("allow_mode_override") is not False:
        raise AssistantV0ContractLoadError("dry_run_mode_override_allowed")

    return AssistantV0Contracts(
        contract_version=ASSISTANT_V0_CONTRACT_VERSION,
        safe_session_tools=safe_session_tools,
        adapter_required_tools=adapter_required_tools,
        dry_run_fixed_executor_mode=DRY_RUN_FIXED_EXECUTOR_MODE,
        diagnostics={
            "adapter_required_tool_count": len(adapter_required_tools),
            "forbidden_tool_count": len(forbidden),
            "safe_tool_count": len(safe_session_tools),
            "target_component": ASSISTANT_V0_TARGET_COMPONENT,
        },
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssistantV0ContractLoadError("json_object_required")
    return data


def _manifest_tool_names(manifest: dict[str, Any]) -> tuple[str, ...]:
    tools = manifest.get("tools")
    if not isinstance(tools, list):
        raise AssistantV0ContractLoadError("manifest_tools_required")
    names = []
    for item in tools:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise AssistantV0ContractLoadError("manifest_tool_name_required")
        names.append(item["name"])
    return tuple(sorted(names))


def _tool_by_name(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    for item in manifest.get("tools", []):
        if isinstance(item, dict) and item.get("name") == name:
            return item
    raise AssistantV0ContractLoadError(f"tool_missing:{name}")


def _sorted_tuple(value: Any) -> tuple[str, ...]:
    return tuple(sorted(_string_tuple(value)))


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AssistantV0ContractLoadError("string_list_required")
    return tuple(value)
