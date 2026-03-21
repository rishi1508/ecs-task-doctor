"""Tests for output formatters."""

from __future__ import annotations

import json

from rich.console import Console

from ecs_doctor.formatters.console import format_console, format_health_table
from ecs_doctor.formatters.json_fmt import format_health_json, format_json
from ecs_doctor.formatters.markdown import format_health_markdown, format_markdown
from ecs_doctor.models import (
    CheckResult,
    DiagnosisReport,
    HealthSummary,
    Recommendation,
    Severity,
)


def _make_report() -> DiagnosisReport:
    return DiagnosisReport(
        cluster="production",
        service="api-server",
        summary="Container keeps crashing",
        checks=[
            CheckResult(name="Image", severity=Severity.OK, message="Image exists"),
            CheckResult(
                name="Task Status",
                severity=Severity.CRITICAL,
                message="Container exited with code 137",
                details="OOM Kill",
            ),
            CheckResult(
                name="Resources",
                severity=Severity.WARNING,
                message="Memory limit is tight",
            ),
        ],
        recommendations=[
            Recommendation(priority=1, text="Increase memory to 1024MB"),
            Recommendation(priority=2, text="Add --max-old-space-size flag"),
        ],
        log_hint="aws logs tail /ecs/api-server --since 1h",
    )


def _make_health_summaries() -> list[HealthSummary]:
    return [
        HealthSummary(
            service_name="api-server",
            running_count=2,
            desired_count=2,
            status="healthy",
        ),
        HealthSummary(
            service_name="worker",
            running_count=0,
            desired_count=1,
            status="down",
        ),
        HealthSummary(
            service_name="frontend",
            running_count=1,
            desired_count=3,
            status="degraded",
            last_event="unable to place a task",
        ),
    ]


class TestJsonFormatter:
    def test_format_json_valid(self):
        """Should produce valid JSON."""
        report = _make_report()
        output = format_json(report)
        data = json.loads(output)
        assert data["cluster"] == "production"
        assert data["service"] == "api-server"
        assert len(data["checks"]) == 3
        assert len(data["recommendations"]) == 2

    def test_format_json_severity_values(self):
        """Should use severity enum values."""
        report = _make_report()
        data = json.loads(format_json(report))
        severities = [c["severity"] for c in data["checks"]]
        assert "ok" in severities
        assert "critical" in severities
        assert "warning" in severities

    def test_format_health_json(self):
        """Should produce valid health JSON."""
        output = format_health_json(_make_health_summaries())
        data = json.loads(output)
        assert len(data["services"]) == 3


class TestMarkdownFormatter:
    def test_format_markdown_header(self):
        """Should include a proper markdown header."""
        report = _make_report()
        output = format_markdown(report)
        assert "# ECS Task Doctor" in output
        assert "production" in output
        assert "api-server" in output

    def test_format_markdown_checks(self):
        """Should format checks with icons."""
        report = _make_report()
        output = format_markdown(report)
        assert "\u2705" in output  # OK
        assert "\u274c" in output  # Critical
        assert "\u26a0\ufe0f" in output  # Warning

    def test_format_markdown_recommendations(self):
        """Should list recommendations."""
        report = _make_report()
        output = format_markdown(report)
        assert "1. Increase memory" in output
        assert "2. Add --max-old-space-size" in output

    def test_format_health_markdown_table(self):
        """Should produce a markdown table."""
        output = format_health_markdown(_make_health_summaries())
        assert "| Service |" in output
        assert "api-server" in output


class TestConsoleFormatter:
    def test_format_console_no_error(self):
        """Should print without errors."""
        report = _make_report()
        console = Console(file=None, force_terminal=True, width=100)
        # Should not raise
        format_console(report, console=console)

    def test_format_health_table_no_error(self):
        """Should print health table without errors."""
        summaries = _make_health_summaries()
        console = Console(file=None, force_terminal=True, width=100)
        format_health_table(summaries, console=console)
