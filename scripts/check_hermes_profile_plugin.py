from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _default_suite_root() -> Path | None:
    configured = os.environ.get("PMX_SUITE_ROOT", "").strip()
    if configured:
        return Path(configured)
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "scripts" / "check_hermes_profile_plugin.py").is_file():
        return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the integration-suite Hermes profile check from an adapter checkout.",
        add_help=False,
    )
    parser.add_argument(
        "--suite-root",
        type=Path,
        default=_default_suite_root(),
        help="Integration repository root. Defaults to PMX_SUITE_ROOT or an enclosing suite checkout.",
    )
    args, forwarded = parser.parse_known_args(argv)
    if args.suite_root is None:
        print(
            "missing --suite-root or PMX_SUITE_ROOT; "
            "the Hermes profile check requires the integration repository"
        )
        return 2

    script = args.suite_root.resolve() / "scripts" / "check_hermes_profile_plugin.py"
    if not script.is_file() or script.resolve() == Path(__file__).resolve():
        print(f"integration Hermes profile check not found: {script}")
        return 2

    completed = subprocess.run(
        [sys.executable, str(script), *forwarded],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
