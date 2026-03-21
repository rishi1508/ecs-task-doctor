"""Check VPC networking configuration for Fargate awsvpc tasks."""

from __future__ import annotations

from typing import Any

from botocore.exceptions import ClientError

from ecs_doctor.models import CheckResult, Severity
from ecs_doctor.utils.aws import get_client, handle_aws_error


def _get_network_config(
    ecs_client: Any, cluster: str, service: str | None
) -> dict[str, Any] | None:
    """Get network configuration from service.

    Args:
        ecs_client: boto3 ECS client.
        cluster: Cluster name.
        service: Service name.

    Returns:
        awsvpcConfiguration dict or None.
    """
    if not service:
        return None

    try:
        resp = ecs_client.describe_services(cluster=cluster, services=[service])
        services = resp.get("services", [])
        if not services:
            return None

        net_config = services[0].get("networkConfiguration", {})
        return net_config.get("awsvpcConfiguration")
    except ClientError:
        return None


def check_networking(
    ecs_client: Any,
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
) -> list[CheckResult]:
    """Check VPC/subnet/security group configuration.

    Args:
        ecs_client: boto3 ECS client.
        cluster: ECS cluster name.
        service: Optional service name.
        task_arn: Optional task ARN.

    Returns:
        List of CheckResult findings.
    """
    results: list[CheckResult] = []

    vpc_config = _get_network_config(ecs_client, cluster, service)

    if not vpc_config:
        results.append(
            CheckResult(
                name="Networking",
                severity=Severity.OK,
                message="No awsvpc network configuration found — skipping network checks",
            )
        )
        return results

    subnets = vpc_config.get("subnets", [])
    security_groups = vpc_config.get("securityGroups", [])

    if not subnets:
        results.append(
            CheckResult(
                name="Networking",
                severity=Severity.CRITICAL,
                message="No subnets configured in network configuration",
            )
        )
        return results

    ec2_client = get_client("ec2")

    # Check subnets
    try:
        subnet_resp = ec2_client.describe_subnets(SubnetIds=subnets)
        for subnet in subnet_resp.get("Subnets", []):
            available_ips = subnet.get("AvailableIpAddressCount", 0)
            subnet_id = subnet.get("SubnetId", "")
            az = subnet.get("AvailabilityZone", "")

            if available_ips == 0:
                results.append(
                    CheckResult(
                        name="Networking",
                        severity=Severity.CRITICAL,
                        message=f"Subnet {subnet_id} ({az}) has no available IP addresses",
                    )
                )
            elif available_ips < 5:
                results.append(
                    CheckResult(
                        name="Networking",
                        severity=Severity.WARNING,
                        message=(
                            f"Subnet {subnet_id} ({az}) has only "
                            f"{available_ips} available IPs"
                        ),
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Networking",
                        severity=Severity.OK,
                        message=f"Subnet {subnet_id} ({az}) has {available_ips} available IPs",
                    )
                )
    except ClientError as e:
        results.append(
            CheckResult(
                name="Networking",
                severity=Severity.ERROR,
                message=f"Failed to check subnets: {handle_aws_error(e)}",
            )
        )

    # Check security groups
    if security_groups:
        try:
            sg_resp = ec2_client.describe_security_groups(GroupIds=security_groups)
            for sg in sg_resp.get("SecurityGroups", []):
                sg_id = sg.get("GroupId", "")
                sg_name = sg.get("GroupName", "")

                # Check for egress rules (needed for ECR/internet access)
                egress_rules = sg.get("IpPermissionsEgress", [])
                has_egress = bool(egress_rules)

                if not has_egress:
                    results.append(
                        CheckResult(
                            name="Networking",
                            severity=Severity.CRITICAL,
                            message=(
                                f"Security group {sg_id} ({sg_name}) "
                                f"has no egress rules — cannot reach ECR or internet"
                            ),
                        )
                    )
                else:
                    results.append(
                        CheckResult(
                            name="Networking",
                            severity=Severity.OK,
                            message=f"Security group {sg_id} ({sg_name}) has egress rules",
                        )
                    )
        except ClientError as e:
            results.append(
                CheckResult(
                    name="Networking",
                    severity=Severity.ERROR,
                    message=f"Failed to check security groups: {handle_aws_error(e)}",
                )
            )

    if not results:
        results.append(
            CheckResult(
                name="Networking",
                severity=Severity.OK,
                message="Network configuration looks correct",
            )
        )

    return results
