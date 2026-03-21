"""Markdown output formatter."""

from __future__ import annotations

from ecs_doctor.models import DiagnosisReport, HealthSummary, Severity

SEVERITY_ICONS = {
    Severity.OK: "\u2705",
    Severity.WARNING: "\u26a0\ufe0f",
    Severity.CRITICAL: "\u274c",
    Severity.ERROR: "\u274c",
}


def format_markdown(report: DiagnosisReport) -> str:
    """Format a diagnosis report as Markdown.

    Args:
        report: The diagnosis report.

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    # Header
    lines.append("# ECS Task Doctor \u2014 Diagnosis Report")
    lines.append("")
    lines.append(f"**Cluster:** {report.cluster}  ")
    if report.service:
        lines.append(f"**Service:** {report.service}  ")
    if report.task_arn:
        lines.append(f"**Task:** {report.task_arn}  ")
    lines.append("")

    # Summary
    if report.summary:
        has_critical = any(c.severity == Severity.CRITICAL for c in report.checks)
        if has_critical:
            lines.append(f"> \U0001f534 **CRITICAL:** {report.summary}")
        else:
            lines.append(f"> {report.summary}")
        lines.append("")

    # Checks
    lines.append("## Checks")
    lines.append("")
    for check in report.checks:
        icon = SEVERITY_ICONS[check.severity]
        line = f"- {icon} **{check.name}**: {check.message}"
        lines.append(line)
        if check.details:
            lines.append(f"  - {check.details}")
    lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("## Recommendations")
        lines.append("")
        for rec in sorted(report.recommendations, key=lambda r: r.priority):
            lines.append(f"{rec.priority}. {rec.text}")
        lines.append("")

    # Log hint
    if report.log_hint:
        lines.append(f"**Full logs:** `{report.log_hint}`")
        lines.append("")

    return "\n".join(lines)


def format_health_markdown(summaries: list[HealthSummary]) -> str:
    """Format health summaries as a Markdown table.

    Args:
        summaries: List of health summaries.

    Returns:
        Markdown table string.
    """
    lines: list[str] = []
    lines.append("# ECS Cluster Health")
    lines.append("")
    lines.append("| Service | Status | Running | Desired |")
    lines.append("|---------|--------|---------|---------|")

    for s in summaries:
        if s.running_count == s.desired_count and s.desired_count > 0:
            status = "\u2705 Healthy"
        elif s.running_count == 0:
            status = "\u274c Down"
        else:
            status = "\u26a0\ufe0f Degraded"

        lines.append(f"| {s.service_name} | {status} | {s.running_count} | {s.desired_count} |")

    lines.append("")
    return "\n".join(lines)
