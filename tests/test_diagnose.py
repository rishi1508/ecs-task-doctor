"""Tests for the core diagnosis engine."""

from __future__ import annotations

import boto3
from moto import mock_aws

from ecs_doctor.diagnose import get_cluster_health, run_diagnosis, scan_cluster


@mock_aws
def test_run_diagnosis_with_service(aws_credentials):
    """Should run all checks and build a report for a service."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx:latest",
                "cpu": 256,
                "memory": 512,
                "essential": True,
            }
        ],
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    report = run_diagnosis(
        cluster="test-cluster",
        service="test-service",
        region="us-east-1",
    )

    assert report.cluster == "test-cluster"
    assert report.service == "test-service"
    assert len(report.checks) > 0
    assert report.summary


@mock_aws
def test_run_diagnosis_with_task(aws_credentials):
    """Should run diagnosis for a task ARN (even if task is not found, checks run gracefully)."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    # Use a fake task ARN — checks should handle missing tasks gracefully
    task_arn = "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123"

    report = run_diagnosis(
        cluster="test-cluster",
        task_arn=task_arn,
        region="us-east-1",
    )

    assert report.cluster == "test-cluster"
    assert report.task_arn == task_arn
    assert len(report.checks) > 0


@mock_aws
def test_scan_cluster_with_unhealthy(aws_credentials):
    """Should find and diagnose unhealthy services."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx:latest",
                "cpu": 256,
                "memory": 512,
                "essential": True,
            }
        ],
    )

    # Service with desiredCount > 0 but runningCount = 0 (moto default)
    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    reports = scan_cluster(cluster="test-cluster", region="us-east-1")
    # Moto sets runningCount=0, so it looks unhealthy
    assert len(reports) >= 1


@mock_aws
def test_scan_empty_cluster(aws_credentials):
    """Should return empty list for cluster with no services."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    reports = scan_cluster(cluster="test-cluster", region="us-east-1")
    assert len(reports) == 0


@mock_aws
def test_get_cluster_health(aws_credentials):
    """Should return health summaries."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx:latest",
                "cpu": 256,
                "memory": 512,
                "essential": True,
            }
        ],
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=2,
    )

    summaries = get_cluster_health(cluster="test-cluster", region="us-east-1")
    assert len(summaries) == 1
    assert summaries[0].service_name == "test-service"
    assert summaries[0].desired_count == 2


@mock_aws
def test_get_cluster_health_empty(aws_credentials):
    """Should return empty list for cluster with no services."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    summaries = get_cluster_health(cluster="test-cluster", region="us-east-1")
    assert len(summaries) == 0
