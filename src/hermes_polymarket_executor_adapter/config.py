from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class ExecutorConfig:
    base_url: str
    service_token: str
    admin_token: str | None = None
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("executor base_url must be an absolute http(s) URL")
        if self.timeout_seconds <= 0:
            raise ValueError("executor timeout_seconds must be positive")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/"))

    @classmethod
    def from_env(cls) -> "ExecutorConfig":
        base_url = os.environ.get("PM_EXEC_SERVICE_URL")
        if not base_url:
            raise RuntimeError("PM_EXEC_SERVICE_URL is required")
        service_token = os.environ.get("PM_EXEC_SERVICE_TOKEN")
        if not service_token:
            raise RuntimeError("PM_EXEC_SERVICE_TOKEN is required")
        return cls(
            base_url=base_url.rstrip("/"),
            service_token=service_token,
            admin_token=os.environ.get("PM_EXEC_ADMIN_TOKEN"),
        )
