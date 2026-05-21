from __future__ import annotations

import argparse
import hashlib
import json

import pytest

from hermes_polymarket_control.cli import _canary_report


def write_json(path, payload):
    path.write_text(json.dumps(payload, sort_keys=True) + "\n")


def source_candidate_manifest():
    return {
        "artifact": {"sha256": None},
        "release_decision": {"status": "shadow-ready SDK sign-only candidate"},
    }


def test_canary_report_requires_external_artifact_hash_for_source_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, source_candidate_manifest())

    with pytest.raises(SystemExit, match="requires an artifact SHA-256"):
        _canary_report(
            argparse.Namespace(
                manifest=str(manifest),
                artifact_sha256=None,
                evidence_sidecar=None,
                approval=None,
                blocked_reason=None,
            )
        )


def test_canary_report_accepts_evidence_sidecar_for_source_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    write_json(manifest, source_candidate_manifest())
    sidecar = tmp_path / "artifact.zip.evidence.json"
    artifact_hash = "a" * 64
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    write_json(
        sidecar,
        {
            "artifact": {"sha256": artifact_hash},
            "canonical_evidence": {"manifest_sha256": manifest_hash},
        },
    )

    report = _canary_report(
        argparse.Namespace(
            manifest=str(manifest),
            artifact_sha256=None,
            evidence_sidecar=str(sidecar),
            approval=None,
            blocked_reason=None,
        )
    )

    assert report.evidence.artifact_sha256 == artifact_hash
    assert report.evidence.evidence_manifest_sha256 == manifest_hash
    assert report.live_submit_allowed is False
