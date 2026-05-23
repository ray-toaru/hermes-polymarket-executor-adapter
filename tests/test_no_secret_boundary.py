from __future__ import annotations

from pathlib import Path


def test_executor_adapter_has_no_secret_or_live_clob_terms():
    root = Path(__file__).resolve().parents[1]
    forbidden = [a + b for a, b in [
        ("POLYMARKET", "_PRIVATE_KEY"),
        ("POLY_API", "_SECRET"),
        ("POLY_API", "_PASSPHRASE"),
        ("private", "_key"),
        ("clob", "_secret"),
        ("api", "_secret"),
        ("raw", "_signature"),
        ("raw", "_signed_payload"),
        ("SignedOrder", "Envelope"),
        ("post", "_order("),
        ("post", "_orders("),
    ]]
    allowlist = {
        root / "AGENTS.md",
        root / "README.md",
        root / "docs" / "ROADMAP.md",
    }

    failures = []
    for path in sorted((root / "src").rglob("*.py")):
        if path in allowlist:
            continue
        text = path.read_text()
        for token in forbidden:
            if token in text:
                failures.append(f"{path.relative_to(root)} contains {token}")
    assert not failures
