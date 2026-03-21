"""CloudWatch log analysis for failed containers."""

from __future__ import annotations

import re
from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import get_client, handle_aws_error

ERROR_PATTERNS: list[tuple[str, str]] = [
    (r"out of memory|OOM|oom.kill|JavaScript heap out of memory", "Out of memory error"),
    (r"connection refused|ECONNREFUSED", "Connection refused"),
    (r"permission denied|EACCES|AccessDenied", "Permission denied"),
    (r"no such file|ENOENT|FileNotFoundError|ModuleNotFoundError", "File or module not found"),
    (r"segfault|segmentation fault|SIGSEGV", "Segmentation fault"),
    (r"exec format error", "Wrong architecture — image built for different platform"),
    (r"fatal|panic|FATAL|PANIC", "Fatal error or panic"),
    (r"bind: address already in use|EADDRINUSE", "Port already in use"),
]


def _get_log_config(
    ecs_client: Any, cluster: str, task_arn: str | None, service: str | None
) -> dict[str, Any] | None:
    """Retrieve the log configuration from a task definition.

    Args:
        ecs_client: boto3 ECS client.
        cluster: Cluster name.
        task_arn: Optional task ARN.
        service: Optional service name.

    Returns:
        The log configuration dict or None.
    """
    try:
        task_def_arn = None

        if task_arn:
            resp = ecs_client.describe_tasks(cluster=cluster, tasks=[task_arn])
            tasks = resp.get("tasks", [])
            if tasks:
                task_def_arn = tasks[0].get("taskDefinitionArn")
        elif service:
            resp = ecs_client.describe_services(cluster=cluster, services=[service])
            services = resp.get("services", [])
            if services:
                task_def_arn = services[0].get("taskDefinition")

        if not task_def_arn:
            return None

        td_resp = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
        td = td_resp.get("taskDefinition", {})
        containers = td.get("containerDefinitions", [])

        if containers:
            return containers[0].get("logConfiguration")
    except ClientError:
        return None
    return None


def check_logs(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Analyze CloudWatch logs for error patterns.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []

    log_config = _get_log_config(ecs_client, cluster, task_arn, service)

    if not log_config:
        results.append(
            CheckResult(
                name="Logs",
                severity=Severity.WARNING,
                message="Could not determine log configuration from task definition",
            )
        )
        return results

    if log_config.get("logDriver") != "awslogs":
        results.append(
            CheckResult(
                name="Logs",
                severity=Severity.OK,
                message=f"Log driver is '{log_config.get('logDriver')}', not awslogs — skipping",
            )
        )
        return results

    options = log_config.get("options", {})
    log_group = options.get("awslogs-group")
    region = options.get("awslogs-region", "us-east-1")
    stream_prefix = options.get("awslogs-stream-prefix", "")

    if not log_group:
        results.append(
            CheckResult(
                name="Logs",
                severity=Severity.WARNING,
                message="No log group configured in task definition",
            )
        )
        return results

    try:
        logs_client = get_client("logs", region=region)

        # Get recent log streams
        # Note: AWS doesn't allow orderBy=LastEventTime with logStreamNamePrefix
        if stream_prefix:
            kwargs: dict[str, Any] = {
                "logGroupName": log_group,
                "logStreamNamePrefix": stream_prefix,
                "descending": True,
                "limit": 3,
            }
        else:
            kwargs = {
                "logGroupName": log_group,
                "orderBy": "LastEventTime",
                "descending": True,
                "limit": 3,
            }

        streams_resp = logs_client.describe_log_streams(**kwargs)
        streams = streams_resp.get("logStreams", [])

        if not streams:
            results.append(
                CheckResult(
                    name="Logs",
                    severity=Severity.WARNING,
                    message=f"No log streams found in {log_group}",
                )
            )
            return results

        # Read recent events from the most recent stream
        stream_name = streams[0]["logStreamName"]
        events_resp = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            limit=50,
            startFromHead=False,
        )
        log_events = events_resp.get("events", [])

        if not log_events:
            results.append(
                CheckResult(
                    name="Logs",
                    severity=Severity.OK,
                    message="No recent log events found",
                )
            )
            return results

        # Scan for error patterns
        errors_found: list[tuple[str, str]] = []
        for event in log_events:
            msg = event.get("message", "")
            for pattern, description in ERROR_PATTERNS:
                if re.search(pattern, msg, re.IGNORECASE):
                    errors_found.append((description, msg.strip()))
                    break

        if errors_found:
            # Deduplicate by description
            seen: set[str] = set()
            for desc, line in errors_found:
                if desc not in seen:
                    seen.add(desc)
                    results.append(
                        CheckResult(
                            name="Logs",
                            severity=Severity.CRITICAL,
                            message=f"Log error: {desc}",
                            details=line[:200],
                        )
                    )
        else:
            results.append(
                CheckResult(
                    name="Logs",
                    severity=Severity.OK,
                    message="No known error patterns found in recent logs",
                )
            )

        # Add log hint
        results.append(
            CheckResult(
                name="Logs",
                severity=Severity.OK,
                message=f"Full logs: aws logs tail {log_group} --since 1h",
            )
        )

    except ClientError as e:
        error_code = e.response["Error"].get("Code", "")
        if error_code == "ResourceNotFoundException":
            results.append(
                CheckResult(
                    name="Logs",
                    severity=Severity.WARNING,
                    message=f"Log group '{log_group}' does not exist",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Logs",
                    severity=Severity.ERROR,
                    message=f"Failed to check logs: {handle_aws_error(e)}",
                )
            )

    return results
