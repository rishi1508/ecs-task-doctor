"""Check ECR image availability."""

from __future__ import annotations

import re
from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import get_client, handle_aws_error

ECR_PATTERN = re.compile(
    r"^(\d+)\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com/([^:@]+)(?::([^@]+))?(?:@(.+))?$"
)


def _parse_ecr_uri(uri: str) -> dict[str, str] | None:
    """Parse an ECR image URI into components.

    Args:
        uri: The full ECR image URI.

    Returns:
        Dict with account, region, repo, tag/digest, or None if not ECR.
    """
    match = ECR_PATTERN.match(uri)
    if not match:
        return None
    return {
        "account": match.group(1),
        "region": match.group(2),
        "repo": match.group(3),
        "tag": match.group(4) or "latest",
        "digest": match.group(5) or "",
    }


def _get_images_from_task_def(
    ecs_client: Any, cluster: str, service: str | None, task_arn: str | None
) -> list[str]:
    """Extract image URIs from the task definition.

    Args:
        ecs_client: boto3 ECS client.
        cluster: Cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        List of image URI strings.
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
            return []

        td_resp = ecs_client.describe_task_definition(taskDefinition=task_def_arn)
        containers = td_resp["taskDefinition"].get("containerDefinitions", [])
        return [c["image"] for c in containers if c.get("image")]
    except ClientError:
        return []


def check_image(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Verify ECR images exist and are pullable.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []
    images = _get_images_from_task_def(ecs_client, cluster, service, task_arn)

    if not images:
        results.append(
            CheckResult(
                name="Image",
                severity=Severity.WARNING,
                message="Could not determine container images from task definition",
            )
        )
        return results

    for image_uri in images:
        parsed = _parse_ecr_uri(image_uri)
        if not parsed:
            results.append(
                CheckResult(
                    name="Image",
                    severity=Severity.OK,
                    message=f"Image '{image_uri}' is not an ECR image — skipping ECR checks",
                )
            )
            continue

        try:
            ecr_client = get_client("ecr", region=parsed["region"])

            # Check if repository exists
            ecr_client.describe_repositories(
                registryId=parsed["account"],
                repositoryNames=[parsed["repo"]],
            )

            # Check if image exists
            image_id: dict[str, str] = {}
            if parsed["digest"]:
                image_id["imageDigest"] = parsed["digest"]
            else:
                image_id["imageTag"] = parsed["tag"]

            img_resp = ecr_client.describe_images(
                registryId=parsed["account"],
                repositoryName=parsed["repo"],
                imageIds=[image_id],
            )

            if img_resp.get("imageDetails"):
                results.append(
                    CheckResult(
                        name="Image",
                        severity=Severity.OK,
                        message=f"Image {image_uri} — exists and pullable",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Image",
                        severity=Severity.CRITICAL,
                        message=f"Image {image_uri} — not found in ECR",
                    )
                )

        except ClientError as e:
            code = e.response["Error"].get("Code", "")
            if code == "RepositoryNotFoundException":
                results.append(
                    CheckResult(
                        name="Image",
                        severity=Severity.CRITICAL,
                        message=f"ECR repository '{parsed['repo']}' not found",
                    )
                )
            elif code == "ImageNotFoundException":
                results.append(
                    CheckResult(
                        name="Image",
                        severity=Severity.CRITICAL,
                        message=f"Image tag '{parsed['tag']}' not found in '{parsed['repo']}'",
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Image",
                        severity=Severity.ERROR,
                        message=f"Failed to check image: {handle_aws_error(e)}",
                    )
                )

    return results
