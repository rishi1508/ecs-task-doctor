"""Check IAM roles and permissions for ECS tasks."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import get_client, handle_aws_error

REQUIRED_EXECUTION_POLICIES = [
    "ecr:GetAuthorizationToken",
    "ecr:BatchCheckLayerAvailability",
    "ecr:GetDownloadUrlForLayer",
    "ecr:BatchGetImage",
    "logs:CreateLogStream",
    "logs:PutLogEvents",
]


def _get_task_def(
    ecs_client: Any, cluster: str, service: str | None, task_arn: str | None
) -> dict[str, Any] | None:
    """Retrieve the task definition.

    Args:
        ecs_client: boto3 ECS client.
        cluster: Cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        Task definition dict or None.
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
        return td_resp.get("taskDefinition")
    except ClientError:
        return None


def _check_role_exists(iam_client: Any, role_name: str) -> tuple[bool, str]:
    """Check if an IAM role exists.

    Args:
        iam_client: boto3 IAM client.
        role_name: The role name to check.

    Returns:
        Tuple of (exists, error_message).
    """
    try:
        iam_client.get_role(RoleName=role_name)
        return True, ""
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            return False, f"Role '{role_name}' does not exist"
        return False, handle_aws_error(e)


def _extract_role_name(role_arn: str) -> str:
    """Extract role name from ARN or return as-is.

    Args:
        role_arn: IAM role ARN or name.

    Returns:
        The role name.
    """
    if "/" in role_arn:
        return role_arn.split("/")[-1]
    return role_arn


def check_iam(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Verify IAM roles exist and have required permissions.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []
    task_def = _get_task_def(ecs_client, cluster, service, task_arn)

    if not task_def:
        results.append(
            CheckResult(
                name="IAM",
                severity=Severity.WARNING,
                message="Could not retrieve task definition to check IAM roles",
            )
        )
        return results

    iam_client = get_client("iam")
    execution_role = task_def.get("executionRoleArn")
    task_role = task_def.get("taskRoleArn")

    # Check execution role
    if execution_role:
        role_name = _extract_role_name(execution_role)
        exists, err = _check_role_exists(iam_client, role_name)
        if exists:
            results.append(
                CheckResult(
                    name="IAM",
                    severity=Severity.OK,
                    message=f"Task execution role '{role_name}' exists",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="IAM",
                    severity=Severity.CRITICAL,
                    message=f"Task execution role issue: {err}",
                )
            )
    else:
        results.append(
            CheckResult(
                name="IAM",
                severity=Severity.WARNING,
                message="No execution role defined — may fail to pull images or write logs",
            )
        )

    # Check task role
    if task_role:
        role_name = _extract_role_name(task_role)
        exists, err = _check_role_exists(iam_client, role_name)
        if exists:
            results.append(
                CheckResult(
                    name="IAM",
                    severity=Severity.OK,
                    message=f"Task role '{role_name}' exists",
                )
            )
        else:
            results.append(
                CheckResult(
                    name="IAM",
                    severity=Severity.CRITICAL,
                    message=f"Task role issue: {err}",
                )
            )

    # Check for secrets references without secretsmanager permissions
    containers = task_def.get("containerDefinitions", [])
    has_secrets = any(c.get("secrets") for c in containers)
    if has_secrets:
        results.append(
            CheckResult(
                name="IAM",
                severity=Severity.WARNING,
                message=(
                    "Task uses secrets — ensure execution role has "
                    "secretsmanager:GetSecretValue or ssm:GetParameters permissions"
                ),
            )
        )

    if not results:
        results.append(
            CheckResult(
                name="IAM",
                severity=Severity.OK,
                message="IAM configuration looks correct",
            )
        )

    return results
