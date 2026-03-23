"""Click-based CLI for ECS Task Doctor."""

from __future__ import annotations

import sys

import boto3
import click

from ecs_doctor import __version__
from ecs_doctor.diagnose import get_cluster_health, run_diagnosis, scan_cluster
from ecs_doctor.formatters.console import format_console, format_health_table
from ecs_doctor.formatters.json_fmt import format_health_json, format_json
from ecs_doctor.formatters.markdown import format_health_markdown, format_markdown


@click.group()
@click.version_option(version=__version__, prog_name="ecs-doctor")
def main() -> None:
    """ECS Task Doctor — Diagnose why your ECS tasks fail to start or keep crashing."""


@main.command()
@click.option("--cluster", required=True, help="ECS cluster name or ARN.")
@click.option("--service", default=None, help="ECS service name.")
@click.option("--task", default=None, help="Specific task ARN to diagnose.")
@click.option("--region", default=None, help="AWS region override.")
@click.option("--profile", default=None, help="AWS CLI profile to use.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json", "markdown"]),
    default="console",
    help="Output format.",
)
def diagnose(
    cluster: str,
    service: str | None,
    task: str | None,
    region: str | None,
    profile: str | None,
    output_format: str,
) -> None:
    """Diagnose a specific ECS service or task."""
    if profile:
        boto3.setup_default_session(profile_name=profile)

    if not service and not task:
        click.echo("Error: either --service or --task is required.", err=True)
        sys.exit(1)

    try:
        report = run_diagnosis(
            cluster=cluster,
            service=service,
            task_arn=task,
            region=region,
        )
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(format_json(report))
    elif output_format == "markdown":
        click.echo(format_markdown(report))
    else:
        format_console(report)


@main.command()
@click.option("--cluster", required=True, help="ECS cluster name or ARN.")
@click.option("--region", default=None, help="AWS region override.")
@click.option("--profile", default=None, help="AWS CLI profile to use.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json", "markdown"]),
    default="console",
    help="Output format.",
)
def scan(cluster: str, region: str | None, profile: str | None, output_format: str) -> None:
    """Scan all services in a cluster and diagnose unhealthy ones."""
    if profile:
        boto3.setup_default_session(profile_name=profile)

    try:
        reports = scan_cluster(cluster=cluster, region=region)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not reports:
        click.echo("All services in the cluster appear healthy.")
        return

    for report in reports:
        if output_format == "json":
            click.echo(format_json(report))
        elif output_format == "markdown":
            click.echo(format_markdown(report))
        else:
            format_console(report)
            click.echo()


@main.command()
@click.option("--cluster", required=True, help="ECS cluster name or ARN.")
@click.option("--region", default=None, help="AWS region override.")
@click.option("--profile", default=None, help="AWS CLI profile to use.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["console", "json", "markdown"]),
    default="console",
    help="Output format.",
)
def health(cluster: str, region: str | None, profile: str | None, output_format: str) -> None:
    """Quick health check for all services in a cluster."""
    if profile:
        boto3.setup_default_session(profile_name=profile)

    try:
        summaries = get_cluster_health(cluster=cluster, region=region)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not summaries:
        click.echo("No services found in the cluster.")
        return

    if output_format == "json":
        click.echo(format_health_json(summaries))
    elif output_format == "markdown":
        click.echo(format_health_markdown(summaries))
    else:
        format_health_table(summaries)
