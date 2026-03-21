"""Check ECS task stopped reasons and container exit codes."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import handle_aws_error

REASON_MAP: dict[str, str] = {
    "CannotPullContainerError": "ECR/network issue — check image URI and network connectivity",
    "ResourceNotFoundException": "Task definition was deleted — recreate or update the service",
    "OutOfMemoryError": "Container exceeded memory limit — increase memory allocation",
    "CannotStartContainerError": "Container entrypoint/command failed — check Dockerfile CMD",
}

EXIT_CODE_MAP: dict[int, str] = {
    137: "OOM Kill (SIGKILL) — container exceeded memory limit",
    1: "Application error — check application logs",
    126: "Command not executable — check Dockerfile permissions",
    127: "Command not found — check Dockerfile CMD/ENTRYPOINT",
    128: "Invalid exit code — possible signal handling issue",
    139: "Segmentation fault (SIGSEGV) — memory corruption or native code bug",
    143: "Graceful termination (SIGTERM) — task was stopped intentionally",
}


def check_task_status(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Check stopped task reasons and container exit codes.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name or ARN.
        service: Optional service name.
        task_arn: Optional specific task ARN.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []

    try:
        if task_arn:
            task_arns = [task_arn]
        elif service:
            resp = ecs_client.list_tasks(
                cluster=cluster,
                serviceName=service,
                desiredStatus="STOPPED",
                maxResults=5,
            )
            task_arns = resp.get("taskArns", [])
        else:
            resp = ecs_client.list_tasks(
                cluster=cluster,
                desiredStatus="STOPPED",
                maxResults=5,
            )
            task_arns = resp.get("taskArns", [])

        if not task_arns:
            results.append(
                CheckResult(
                    name="Task Status",
                    severity=Severity.OK,
                    message="No recently stopped tasks found",
                )
            )
            return results

        desc = ecs_client.describe_tasks(cluster=cluster, tasks=task_arns)
        tasks = desc.get("tasks", [])

        for task in tasks:
            stopped_reason = task.get("stoppedReason", "")
            task_id = task.get("taskArn", "").split("/")[-1]

            # Check stopped reason
            if stopped_reason:
                severity = Severity.CRITICAL
                detail = stopped_reason
                for pattern, explanation in REASON_MAP.items():
                    if pattern in stopped_reason:
                        detail = f"{stopped_reason} — {explanation}"
                        break

                if "has reached a steady state" in stopped_reason.lower():
                    severity = Severity.OK

                results.append(
                    CheckResult(
                        name="Task Status",
                        severity=severity,
                        message=f"Task {task_id}: {stopped_reason}",
                        details=detail,
                    )
                )

            # Check container exit codes
            for container in task.get("containers", []):
                exit_code = container.get("exitCode")
                container_name = container.get("name", "unknown")
                if exit_code is not None and exit_code != 0:
                    explanation = EXIT_CODE_MAP.get(exit_code, f"Non-zero exit code {exit_code}")
                    results.append(
                        CheckResult(
                            name="Task Status",
                            severity=Severity.CRITICAL,
                            message=(
                                f"Container '{container_name}' exited with code "
                                f"{exit_code} ({explanation})"
                            ),
                            details=container.get("reason", ""),
                        )
                    )

        if not results:
            results.append(
                CheckResult(
                    name="Task Status",
                    severity=Severity.OK,
                    message="No task issues found",
                )
            )

    except ClientError as e:
        results.append(
            CheckResult(
                name="Task Status",
                severity=Severity.ERROR,
                message=f"Failed to check task status: {handle_aws_error(e)}",
            )
        )

    return results
