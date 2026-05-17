from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class ExecutorConfig:
    base_url: str
    service_token: str
    admin_token: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "ExecutorConfig":
        base_url = os.environ.get("PM_EXEC_SERVICE_URL", "http://localhost:8080")
        service_token = os.environ.get("PM_EXEC_SERVICE_TOKEN")
        if not service_token:
            raise RuntimeError("PM_EXEC_SERVICE_TOKEN is required")
        return cls(
            base_url=base_url.rstrip("/"),
            service_token=service_token,
            admin_token=os.environ.get("PM_EXEC_ADMIN_TOKEN"),
        )
