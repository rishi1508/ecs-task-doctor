"""Analyze ECS service events for error patterns."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import handle_aws_error

ERROR_PATTERNS: list[tuple[str, str, Severity]] = [
    (
        r"unable to place a task",
        "Insufficient capacity — check CPU/memory availability or capacity providers",
        Severity.CRITICAL,
    ),
    (
        r"is unable to consistently start tasks",
        "Service is crash-looping — tasks keep starting and stopping",
        Severity.CRITICAL,
    ),
    (
        r"target group .* has no registered targets",
        "No healthy targets registered with load balancer",
        Severity.WARNING,
    ),
    (
        r"was unable to .* because no container instances",
        "No container instances available — scale up ASG or use Fargate",
        Severity.CRITICAL,
    ),
    (
        r"CannotPullContainerError",
        "Cannot pull container image — check ECR permissions and network",
        Severity.CRITICAL,
    ),
    (
        r"port \d+ is already in use",
        "Port conflict — another task is using the same host port",
        Severity.CRITICAL,
    ),
]


def _detect_crash_loop(events: list[dict[str, Any]]) -> CheckResult | None:
    """Detect rapid task start/stop cycles indicating a crash loop.

    Args:
        events: List of ECS service events.

    Returns:
        A CheckResult if crash loop is detected, else None.
    """
    stop_count = 0
    now = datetime.now(timezone.utc)
    for event in events:
        created = event.get("createdAt")
        if created and hasattr(created, "timestamp"):
            age_minutes = (now - created).total_seconds() / 60
        else:
            age_minutes = 999

        msg = event.get("message", "")
        if "has stopped" in msg or "stopped task" in msg.lower():
            if age_minutes < 30:
                stop_count += 1

    if stop_count >= 3:
        return CheckResult(
            name="Service Events",
            severity=Severity.CRITICAL,
            message=f"Crash loop detected: {stop_count} task stops in last 30 minutes",
        )
    return None


def check_service_events(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Analyze recent service events for error patterns.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name or ARN.
        service: Service name (required for this check).
        task_arn: Unused, for interface consistency.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []

    if not service:
        results.append(
            CheckResult(
                name="Service Events",
                severity=Severity.OK,
                message="Skipped — no service specified",
            )
        )
        return results

    try:
        resp = ecs_client.describe_services(cluster=cluster, services=[service])
        services = resp.get("services", [])

        if not services:
            results.append(
                CheckResult(
                    name="Service Events",
                    severity=Severity.ERROR,
                    message=f"Service '{service}' not found in cluster '{cluster}'",
                )
            )
            return results

        svc = services[0]
        events = svc.get("events", [])[:20]

        if not events:
            results.append(
                CheckResult(
                    name="Service Events",
                    severity=Severity.OK,
                    message="No recent service events",
                )
            )
            return results

        # Check for crash loops
        crash_loop = _detect_crash_loop(events)
        if crash_loop:
            results.append(crash_loop)

        # Check event messages against error patterns
        error_found = False
        for event in events[:10]:
            msg = event.get("message", "")
            for pattern, explanation, severity in ERROR_PATTERNS:
                if re.search(pattern, msg, re.IGNORECASE):
                    results.append(
                        CheckResult(
                            name="Service Events",
                            severity=severity,
                            message=explanation,
                            details=msg,
                        )
                    )
                    error_found = True
                    break

        if not error_found and not crash_loop:
            # Check if steady state
            latest_msg = events[0].get("message", "")
            if "has reached a steady state" in latest_msg:
                results.append(
                    CheckResult(
                        name="Service Events",
                        severity=Severity.OK,
                        message="Service has reached a steady state",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Service Events",
                        severity=Severity.OK,
                        message="No error patterns detected in recent events",
                    )
                )

    except ClientError as e:
        results.append(
            CheckResult(
                name="Service Events",
                severity=Severity.ERROR,
                message=f"Failed to check service events: {handle_aws_error(e)}",
            )
        )

    return results
