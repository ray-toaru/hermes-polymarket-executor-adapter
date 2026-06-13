from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_openapi_parity.py"


def load_script():
    spec = importlib.util.spec_from_file_location("check_openapi_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_parity_reports_missing_schema():
    module = load_script()
    failures = module.parity_failures({"components": {"schemas": {}}})
    assert failures == [
        f"OpenAPI schema missing: {schema_name}"
        for schema_name in module.MODEL_BY_SCHEMA
    ]


def test_current_executor_openapi_has_model_parity():
    module = load_script()
    suite_root = Path(__file__).resolve().parents[2]
    openapi = suite_root / "polymarket-execution-engine" / "openapi" / "executor.v1.yaml"
    if not openapi.is_file():
        return
    assert module.parity_failures(module.load_spec(openapi)) == []


def test_committed_executor_openapi_snapshot_has_model_parity():
    module = load_script()
    openapi = Path(__file__).resolve().parents[1] / "contracts" / "executor.v1.yaml"
    assert module.parity_failures(module.load_spec(openapi)) == []
