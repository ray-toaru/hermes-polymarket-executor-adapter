from __future__ import annotations

import argparse
import json

from .config import ExecutorConfig
from .client import ExecutorClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes Polymarket control-plane client")
    parser.add_argument("command", choices=["health"])
    args = parser.parse_args()

    config = ExecutorConfig.from_env()
    client = ExecutorClient(config)
    try:
        if args.command == "health":
            print(json.dumps(client.health().model_dump(mode="json"), indent=2, sort_keys=True))
            return 0
    finally:
        client.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
