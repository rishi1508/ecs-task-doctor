"""JSON output formatter."""

from __future__ import annotations

import json
from typing import Any

from ecs_doctor.models import DiagnosisReport, HealthSummary


def _report_to_dict(report: DiagnosisReport) -> dict[str, Any]:
    """Convert a DiagnosisReport to a JSON-serializable dict.

    Args:
        report: The diagnosis report.

    Returns:
        A dictionary representation.
    """
    return {
        "cluster": report.cluster,
        "service": report.service,
        "task_arn": report.task_arn,
        "summary": report.summary,
        "checks": [
            {
                "name": c.name,
                "severity": c.severity.value,
                "message": c.message,
                "details": c.details,
            }
            for c in report.checks
        ],
        "recommendations": [
            {"priority": r.priority, "text": r.text} for r in report.recommendations
        ],
        "log_hint": report.log_hint,
    }


def format_json(report: DiagnosisReport) -> str:
    """Format a diagnosis report as JSON.

    Args:
        report: The diagnosis report.

    Returns:
        JSON string.
    """
    return json.dumps(_report_to_dict(report), indent=2)


def format_health_json(summaries: list[HealthSummary]) -> str:
    """Format health summaries as JSON.

    Args:
        summaries: List of health summaries.

    Returns:
        JSON string.
    """
    data = [
        {
            "service": s.service_name,
            "running_count": s.running_count,
            "desired_count": s.desired_count,
            "status": s.status,
            "last_event": s.last_event,
        }
        for s in summaries
    ]
    return json.dumps({"services": data}, indent=2)
