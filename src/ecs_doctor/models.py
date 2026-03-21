"""Data models for diagnosis results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    """Severity level for a check finding."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


@dataclass
class CheckResult:
    """Result from a single diagnostic check."""

    name: str
    severity: Severity
    message: str
    details: str | None = None


@dataclass
class Recommendation:
    """An actionable recommendation."""

    priority: int
    text: str


@dataclass
class DiagnosisReport:
    """Complete diagnosis report for a service or task."""

    cluster: str
    service: str | None = None
    task_arn: str | None = None
    summary: str = ""
    checks: list[CheckResult] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    log_hint: str | None = None


@dataclass
class HealthSummary:
    """Summary health info for a single service."""

    service_name: str
    running_count: int
    desired_count: int
    status: str
    last_event: str | None = None
