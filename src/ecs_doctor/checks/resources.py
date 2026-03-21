"""Check CPU/memory constraints and cluster capacity."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import handle_aws_error


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


def check_resources(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Check CPU/memory constraints and resource availability.

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
                name="Resources",
                severity=Severity.WARNING,
                message="Could not retrieve task definition to check resources",
            )
        )
        return results

    # Check task-level resources
    task_cpu = task_def.get("cpu")
    task_memory = task_def.get("memory")
    launch_type = task_def.get("requiresCompatibilities", [])
    is_fargate = "FARGATE" in launch_type

    if is_fargate and (not task_cpu or not task_memory):
        results.append(
            CheckResult(
                name="Resources",
                severity=Severity.CRITICAL,
                message="Fargate tasks require task-level cpu and memory to be set",
            )
        )
        return results

    # Check container-level resources
    containers = task_def.get("containerDefinitions", [])
    total_container_memory = 0
    total_container_cpu = 0

    for container in containers:
        name = container.get("name", "unknown")
        mem_limit = container.get("memory", 0)
        mem_reservation = container.get("memoryReservation", 0)
        cpu = container.get("cpu", 0)

        total_container_memory += mem_limit or mem_reservation
        total_container_cpu += cpu

        # Check if memory limit equals task memory (tight constraint)
        if task_memory and mem_limit:
            task_mem_int = int(task_memory)
            if mem_limit >= task_mem_int:
                results.append(
                    CheckResult(
                        name="Resources",
                        severity=Severity.WARNING,
                        message=(
                            f"Container '{name}' memory limit ({mem_limit}MB) "
                            f"is at or above task memory ({task_memory}MB)"
                        ),
                        details="Container has no headroom — may OOM under load",
                    )
                )

        # Warn if no memory limit set at all on EC2
        if not is_fargate and not mem_limit and not mem_reservation:
            results.append(
                CheckResult(
                    name="Resources",
                    severity=Severity.WARNING,
                    message=f"Container '{name}' has no memory limit or reservation set",
                )
            )

    # Check cluster capacity for EC2 launch type
    if not is_fargate:
        try:
            ci_resp = ecs_client.list_container_instances(
                cluster=cluster, status="ACTIVE"
            )
            ci_arns = ci_resp.get("containerInstanceArns", [])

            if not ci_arns:
                results.append(
                    CheckResult(
                        name="Resources",
                        severity=Severity.CRITICAL,
                        message="No active container instances in cluster",
                    )
                )
            else:
                ci_desc = ecs_client.describe_container_instances(
                    cluster=cluster, containerInstances=ci_arns
                )
                instances = ci_desc.get("containerInstances", [])

                total_remaining_cpu = 0
                total_remaining_mem = 0
                for ci in instances:
                    for res in ci.get("remainingResources", []):
                        if res["name"] == "CPU":
                            total_remaining_cpu += res.get("integerValue", 0)
                        elif res["name"] == "MEMORY":
                            total_remaining_mem += res.get("integerValue", 0)

                if task_cpu and total_remaining_cpu < int(task_cpu):
                    results.append(
                        CheckResult(
                            name="Resources",
                            severity=Severity.CRITICAL,
                            message=(
                                f"Insufficient CPU: need {task_cpu} units, "
                                f"only {total_remaining_cpu} available"
                            ),
                        )
                    )

                if task_memory and total_remaining_mem < int(task_memory):
                    results.append(
                        CheckResult(
                            name="Resources",
                            severity=Severity.CRITICAL,
                            message=(
                                f"Insufficient memory: need {task_memory}MB, "
                                f"only {total_remaining_mem}MB available"
                            ),
                        )
                    )

        except ClientError as e:
            results.append(
                CheckResult(
                    name="Resources",
                    severity=Severity.ERROR,
                    message=f"Failed to check cluster capacity: {handle_aws_error(e)}",
                )
            )

    if not results:
        results.append(
            CheckResult(
                name="Resources",
                severity=Severity.OK,
                message="Resource configuration looks correct",
            )
        )

    return results
