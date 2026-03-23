"""Tests for the CLI interface."""

from __future__ import annotations

import boto3
from click.testing import CliRunner
from moto import mock_aws

from ecs_doctor import __version__
from ecs_doctor.cli import main


@mock_aws
def test_diagnose_requires_service_or_task(aws_credentials):
    """Should error when neither --service nor --task is given."""
    runner = CliRunner()
    result = runner.invoke(main, ["diagnose", "--cluster", "test"])
    assert result.exit_code != 0
    assert "either --service or --task" in result.output or result.exit_code == 1


@mock_aws
def test_diagnose_with_service(aws_credentials):
    """Should run diagnosis for a service."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "app", "image": "nginx", "cpu": 256, "memory": 512, "essential": True}
        ],
    )
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "diagnose",
            "--cluster",
            "test-cluster",
            "--service",
            "test-service",
            "--region",
            "us-east-1",
        ],
    )
    assert result.exit_code == 0


@mock_aws
def test_diagnose_json_format(aws_credentials):
    """Should output valid JSON."""
    import json

    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "app", "image": "nginx", "cpu": 256, "memory": 512, "essential": True}
        ],
    )
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "diagnose",
            "--cluster",
            "test-cluster",
            "--service",
            "test-service",
            "--format",
            "json",
            "--region",
            "us-east-1",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["cluster"] == "test-cluster"


@mock_aws
def test_diagnose_markdown_format(aws_credentials):
    """Should output markdown."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "app", "image": "nginx", "cpu": 256, "memory": 512, "essential": True}
        ],
    )
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "diagnose",
            "--cluster",
            "test-cluster",
            "--service",
            "test-service",
            "--format",
            "markdown",
            "--region",
            "us-east-1",
        ],
    )
    assert result.exit_code == 0
    assert "# ECS Task Doctor" in result.output


@mock_aws
def test_health_command(aws_credentials):
    """Should run health check."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "app", "image": "nginx", "cpu": 256, "memory": 512, "essential": True}
        ],
    )
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["health", "--cluster", "test-cluster", "--region", "us-east-1"],
    )
    assert result.exit_code == 0


@mock_aws
def test_health_json_format(aws_credentials):
    """Should output health as JSON."""
    import json

    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {"name": "app", "image": "nginx", "cpu": 256, "memory": 512, "essential": True}
        ],
    )
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["health", "--cluster", "test-cluster", "--format", "json", "--region", "us-east-1"],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "services" in data


@mock_aws
def test_scan_command(aws_credentials):
    """Should run scan."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["scan", "--cluster", "test-cluster", "--region", "us-east-1"],
    )
    assert result.exit_code == 0


@mock_aws
def test_version_flag(aws_credentials):
    """Should show version."""
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
