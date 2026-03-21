"""Core diagnosis engine that runs all checks and builds a report."""

from __future__ import annotations

from botocore.exceptions import ClientError

from ecs_doctor.checks import ALL_CHECKS
from ecs_doctor.models import (
    CheckResult,
    DiagnosisReport,
    HealthSummary,
    Recommendation,
    Severity,
)
from ecs_doctor.utils.aws import get_client, handle_aws_error


def _generate_recommendations(checks: list[CheckResult]) -> list[Recommendation]:
    """Generate actionable recommendations from check results.

    Args:
        checks: List of check results from all modules.

    Returns:
        List of prioritized recommendations.
    """
    recs: list[Recommendation] = []
    priority = 1

    for check in checks:
        if check.severity == Severity.CRITICAL:
            if "OOM" in check.message or "memory" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Increase container memory limit in the task definition",
                ))
                priority += 1
            elif "image" in check.message.lower() or "pull" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text=(
                        "Verify the image URI exists and the execution role"
                        " has ECR pull permissions"
                    ),
                ))
                priority += 1
            elif "crash loop" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Check application logs for the root cause of repeated crashes",
                ))
                priority += 1
            elif "capacity" in check.message.lower() or "place a task" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Scale up cluster capacity or switch to Fargate",
                ))
                priority += 1
            elif "subnet" in check.message.lower() and "ip" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Add more subnets or use subnets with available IP addresses",
                ))
                priority += 1
            elif "role" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Create the missing IAM role or fix the role ARN in the task definition",
                ))
                priority += 1
            elif "exit" in check.message.lower():
                recs.append(Recommendation(
                    priority=priority,
                    text="Check application logs for the cause of the non-zero exit code",
                ))
                priority += 1
            else:
                recs.append(Recommendation(
                    priority=priority,
                    text=f"Investigate: {check.message}",
                ))
                priority += 1

    return recs


def _generate_summary(checks: list[CheckResult]) -> str:
    """Generate a one-line summary from check results.

    Args:
        checks: List of check results.

    Returns:
        Summary string.
    """
    critical = [c for c in checks if c.severity == Severity.CRITICAL]
    warnings = [c for c in checks if c.severity == Severity.WARNING]

    if critical:
        return critical[0].message
    elif warnings:
        return f"{len(warnings)} warning(s) found"
    else:
        return "All checks passed — service appears healthy"


def run_diagnosis(
    cluster: str,
    service: str | None = None,
    task_arn: str | None = None,
    region: str | None = None,
) -> DiagnosisReport:
    """Run all diagnostic checks and build a report.

    Args:
        cluster: ECS cluster name or ARN.
        service: Optional service name.
        task_arn: Optional task ARN.
        region: Optional AWS region.

    Returns:
        A complete DiagnosisReport.
    """
    ecs_client = get_client("ecs", region=region)

    all_results: list[CheckResult] = []
    for check_fn in ALL_CHECKS:
        try:
            results = check_fn(
                ecs_client=ecs_client,
                cluster=cluster,
                service=service,
                task_arn=task_arn,
            )
            all_results.extend(results)
        except Exception as e:
            all_results.append(
                CheckResult(
                    name=check_fn.__name__.replace("check_", "").title(),
                    severity=Severity.ERROR,
                    message=f"Check failed unexpectedly: {e}",
                )
            )

    # Build log hint
    log_hint = None
    for r in all_results:
        if r.name == "Logs" and "Full logs:" in r.message:
            log_hint = r.message.replace("Full logs: ", "")
            break

    recommendations = _generate_recommendations(all_results)
    summary = _generate_summary(all_results)

    return DiagnosisReport(
        cluster=cluster,
        service=service,
        task_arn=task_arn,
        summary=summary,
        checks=all_results,
        recommendations=recommendations,
        log_hint=log_hint,
    )


def scan_cluster(
    cluster: str,
    region: str | None = None,
) -> list[DiagnosisReport]:
    """Scan all services in a cluster for issues.

    Args:
        cluster: ECS cluster name or ARN.
        region: Optional AWS region.

    Returns:
        List of diagnosis reports, one per unhealthy service.
    """
    ecs_client = get_client("ecs", region=region)
    reports: list[DiagnosisReport] = []

    try:
        paginator = ecs_client.get_paginator("list_services")
        service_arns: list[str] = []
        for page in paginator.paginate(cluster=cluster):
            service_arns.extend(page.get("serviceArns", []))

        if not service_arns:
            return reports

        # Describe in batches of 10
        for i in range(0, len(service_arns), 10):
            batch = service_arns[i : i + 10]
            resp = ecs_client.describe_services(cluster=cluster, services=batch)

            for svc in resp.get("services", []):
                running = svc.get("runningCount", 0)
                desired = svc.get("desiredCount", 0)
                svc_name = svc.get("serviceName", "")

                # Only diagnose unhealthy services
                if running < desired or desired == 0:
                    report = run_diagnosis(
                        cluster=cluster,
                        service=svc_name,
                        region=region,
                    )
                    reports.append(report)

    except ClientError as e:
        reports.append(
            DiagnosisReport(
                cluster=cluster,
                summary=f"Failed to scan cluster: {handle_aws_error(e)}",
                checks=[
                    CheckResult(
                        name="Scan",
                        severity=Severity.ERROR,
                        message=handle_aws_error(e),
                    )
                ],
            )
        )

    return reports


def get_cluster_health(
    cluster: str,
    region: str | None = None,
) -> list[HealthSummary]:
    """Get health summary for all services in a cluster.

    Args:
        cluster: ECS cluster name or ARN.
        region: Optional AWS region.

    Returns:
        List of HealthSummary for each service.
    """
    ecs_client = get_client("ecs", region=region)
    summaries: list[HealthSummary] = []

    try:
        paginator = ecs_client.get_paginator("list_services")
        service_arns: list[str] = []
        for page in paginator.paginate(cluster=cluster):
            service_arns.extend(page.get("serviceArns", []))

        if not service_arns:
            return summaries

        for i in range(0, len(service_arns), 10):
            batch = service_arns[i : i + 10]
            resp = ecs_client.describe_services(cluster=cluster, services=batch)

            for svc in resp.get("services", []):
                running = svc.get("runningCount", 0)
                desired = svc.get("desiredCount", 0)
                svc_name = svc.get("serviceName", "")
                events = svc.get("events", [])
                last_event = events[0].get("message", "") if events else None

                if running == desired and desired > 0:
                    status = "healthy"
                elif running == 0:
                    status = "down"
                else:
                    status = "degraded"

                summaries.append(
                    HealthSummary(
                        service_name=svc_name,
                        running_count=running,
                        desired_count=desired,
                        status=status,
                        last_event=last_event,
                    )
                )

    except ClientError as e:
        summaries.append(
            HealthSummary(
                service_name="ERROR",
                running_count=0,
                desired_count=0,
                status="error",
                last_event=handle_aws_error(e),
            )
        )

    return summaries
