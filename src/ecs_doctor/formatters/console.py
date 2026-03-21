"""Rich terminal output formatter."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ecs_doctor.models import CheckResult, DiagnosisReport, HealthSummary, Severity

SEVERITY_ICONS = {
    Severity.OK: "[green]\u2705[/green]",
    Severity.WARNING: "[yellow]\u26a0\ufe0f [/yellow]",
    Severity.CRITICAL: "[red]\u274c[/red]",
    Severity.ERROR: "[red]\u274c[/red]",
}

SEVERITY_COLORS = {
    Severity.OK: "green",
    Severity.WARNING: "yellow",
    Severity.CRITICAL: "red",
    Severity.ERROR: "red",
}


def _format_check(check: CheckResult) -> str:
    """Format a single check result line.

    Args:
        check: The check result to format.

    Returns:
        Formatted rich markup string.
    """
    icon = SEVERITY_ICONS[check.severity]
    color = SEVERITY_COLORS[check.severity]
    line = f"  {icon} [bold]{check.name}[/bold]: [{color}]{check.message}[/{color}]"
    return line


def format_console(report: DiagnosisReport, console: Console | None = None) -> None:
    """Print a diagnosis report using Rich formatting.

    Args:
        report: The diagnosis report to format.
        console: Optional Rich Console instance.
    """
    if console is None:
        console = Console()

    # Header panel
    header = Text()
    header.append("ECS Task Doctor \u2014 Diagnosis Report\n", style="bold white")
    header.append(f"Cluster: {report.cluster}  ", style="dim")
    if report.service:
        header.append(f"Service: {report.service}", style="dim")
    elif report.task_arn:
        task_id = report.task_arn.split("/")[-1] if report.task_arn else ""
        header.append(f"Task: {task_id}", style="dim")

    console.print(Panel(header, border_style="blue"))
    console.print()

    # Summary
    if report.summary:
        # Determine summary severity
        has_critical = any(c.severity == Severity.CRITICAL for c in report.checks)
        has_warning = any(c.severity == Severity.WARNING for c in report.checks)

        if has_critical:
            console.print(f"[bold red]\U0001f534 CRITICAL: {report.summary}[/bold red]")
        elif has_warning:
            console.print(f"[bold yellow]\U0001f7e1 WARNING: {report.summary}[/bold yellow]")
        else:
            console.print(f"[bold green]\U0001f7e2 OK: {report.summary}[/bold green]")
        console.print()

    # Checks
    console.print("[bold]\U0001f4cb Checks:[/bold]")
    for check in report.checks:
        console.print(_format_check(check))
    console.print()

    # Recommendations
    if report.recommendations:
        console.print("[bold]\U0001f4a1 Recommendation:[/bold]")
        for rec in sorted(report.recommendations, key=lambda r: r.priority):
            console.print(f"  {rec.priority}. {rec.text}")
        console.print()

    # Log hint
    if report.log_hint:
        console.print(f"[dim]\U0001f4dd Full logs: {report.log_hint}[/dim]")


def format_health_table(summaries: list[HealthSummary], console: Console | None = None) -> None:
    """Print a health summary table.

    Args:
        summaries: List of service health summaries.
        console: Optional Rich Console instance.
    """
    if console is None:
        console = Console()

    table = Table(title="ECS Cluster Health", border_style="blue")
    table.add_column("Service", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Running", justify="right")
    table.add_column("Desired", justify="right")
    table.add_column("Last Event", max_width=60)

    for s in summaries:
        if s.running_count == s.desired_count and s.desired_count > 0:
            status = "[green]\u2705 Healthy[/green]"
        elif s.running_count == 0:
            status = "[red]\u274c Down[/red]"
        else:
            status = "[yellow]\u26a0\ufe0f  Degraded[/yellow]"

        table.add_row(
            s.service_name,
            status,
            str(s.running_count),
            str(s.desired_count),
            (s.last_event or "")[:60],
        )

    console.print(table)
