from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .config import ExecutorConfig
from .client import ExecutorClient
from .models import CanaryApprovalReference, CanaryEvidenceReference
from .tools import build_canary_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Polymarket control-plane client")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health")
    canary = subparsers.add_parser("canary-report")
    canary.add_argument("--manifest", required=True)
    canary.add_argument(
        "--artifact-sha256",
        help="External release artifact SHA-256. Required when the manifest artifact hash is null.",
    )
    canary.add_argument(
        "--evidence-sidecar",
        help="External .zip.evidence.json sidecar binding artifact and canonical evidence hashes.",
    )
    canary.add_argument("--approval")
    canary.add_argument("--blocked-reason", action="append")
    args = parser.parse_args()

    if args.command == "canary-report":
        print(json.dumps(_canary_report(args).model_dump(mode="json"), indent=2, sort_keys=True))
        return 0

    if args.command == "health":
        config = ExecutorConfig.from_env()
        client = ExecutorClient(config)
        try:
            print(json.dumps(client.health().model_dump(mode="json"), indent=2, sort_keys=True))
            return 0
        finally:
            client.close()
    return 1


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canary_report(args: argparse.Namespace):
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    sidecar = json.loads(Path(args.evidence_sidecar).read_text()) if args.evidence_sidecar else {}
    artifact_sha256 = (
        args.artifact_sha256
        or sidecar.get("artifact", {}).get("sha256")
        or manifest.get("artifact", {}).get("sha256")
    )
    evidence_manifest_sha256 = (
        sidecar.get("canonical_evidence", {}).get("manifest_sha256")
        or _sha256(manifest_path)
    )
    if not artifact_sha256:
        raise SystemExit(
            "canary-report requires an artifact SHA-256. The supplied manifest is "
            "source-candidate evidence with artifact.sha256=null; pass "
            "--artifact-sha256 or --evidence-sidecar."
        )
    evidence = CanaryEvidenceReference(
        artifact_sha256=artifact_sha256,
        evidence_manifest_sha256=evidence_manifest_sha256,
        manifest_path=str(manifest_path),
        release_status=manifest.get("release_decision", {}).get("status", "unknown"),
    )
    approval = None
    if args.approval:
        approval_payload = json.loads(Path(args.approval).read_text())
        approval = CanaryApprovalReference(
            approval_id=approval_payload["approval_id"],
            approval_hash=approval_payload["approval_hash"],
            scope=approval_payload["scope"],
            expires_at=approval_payload["expires_at"],
            operator_identity_ref=approval_payload["operator_identity_ref"],
        )
    return build_canary_readiness_report(
        evidence,
        approval=approval,
        blocked_reasons=args.blocked_reason,
    )


if __name__ == "__main__":
    raise SystemExit(main())
