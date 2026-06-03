from __future__ import annotations

from pathlib import Path
import re


def test_executor_adapter_has_no_secret_or_live_clob_terms():
    root = Path(__file__).resolve().parents[1]
    forbidden = {
        "private_key": re.compile(r"private[_-]?key", re.IGNORECASE),
        "api_secret": re.compile(r"api[_-]?secret", re.IGNORECASE),
        "api_passphrase": re.compile(r"api[_-]?passphrase", re.IGNORECASE),
        "clob_secret": re.compile(r"clob[_-]?secret", re.IGNORECASE),
        "raw_signature": re.compile(r"raw[_-]?signature", re.IGNORECASE),
        "raw_signed_payload": re.compile(r"raw[_-]?signed[_-]?payload", re.IGNORECASE),
        "signed_order_envelope": re.compile(
            r"signedorderenvelope|signed[_-]?order[_-]?envelope",
            re.IGNORECASE,
        ),
        "post_order": re.compile(r"post[_-]?order\s*\(", re.IGNORECASE),
        "post_orders": re.compile(r"post[_-]?orders\s*\(", re.IGNORECASE),
    }
    allowlist = {
        root / "tests" / "test_client.py",
        root / "tests" / "test_models.py",
        root / "tests" / "test_no_secret_boundary.py",
    }

    failures = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".md", ".toml", ".yml", ".yaml", ".txt"}:
            continue
        if path in allowlist:
            continue
        scanned += 1
        text = path.read_text(errors="ignore")
        for name, pattern in forbidden.items():
            if pattern.search(text):
                failures.append(f"{path.relative_to(root)} contains {name}")
    assert scanned > 0
    assert not failures
