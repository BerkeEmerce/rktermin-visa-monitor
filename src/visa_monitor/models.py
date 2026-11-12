from dataclasses import dataclass, field
from enum import StrEnum

class Status(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    CAPTCHA_FAILED = "CAPTCHA_FAILED"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    PARSE_ERROR = "PARSE_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    PARTIAL_CHECK = "PARTIAL_CHECK"

class CheckError(Exception):
    def __init__(self, status, reason, retry_after=0):
        super().__init__(reason)
        self.status = Status(status)
        self.reason = reason
        self.retry_after = retry_after

@dataclass
class CheckResult:
    status: Status
    months: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    error: str | None = None
    reason: str | None = None
    retry_after: float = 0
    captcha: dict = field(default_factory=dict)

    @property
    def complete(self):
        return self.status in (Status.AVAILABLE, Status.UNAVAILABLE)
