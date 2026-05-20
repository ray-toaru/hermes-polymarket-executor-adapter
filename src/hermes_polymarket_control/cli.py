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
    evidence = CanaryEvidenceReference(
        artifact_sha256=manifest["artifact"]["sha256"],
        evidence_manifest_sha256=_sha256(manifest_path),
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
