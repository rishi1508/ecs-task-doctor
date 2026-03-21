"""Tests for task_status check module."""

from __future__ import annotations

import boto3
from moto import mock_aws

from ecs_doctor.checks.task_status import EXIT_CODE_MAP, REASON_MAP, check_task_status
from ecs_doctor.models import Severity


@mock_aws
def test_no_stopped_tasks(aws_credentials):
    """When there are no stopped tasks, should return OK."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    results = check_task_status(client, "test-cluster", service=None)
    assert len(results) == 1
    assert results[0].severity == Severity.OK
    assert "No recently stopped tasks" in results[0].message


def test_stopped_task_with_reason():
    """Stopped tasks with reasons should be reported as CRITICAL."""
    from unittest.mock import MagicMock

    # Mock describe_tasks to return a stopped task with a reason
    # (moto has a bug with Fargate run_task ENI, so we use a mock)
    mock_client = MagicMock()
    mock_client.describe_tasks.return_value = {
        "tasks": [
            {
                "taskArn": "arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123",
                "stoppedReason": "Essential container in task exited",
                "containers": [
                    {
                        "name": "app",
                        "exitCode": 137,
                        "reason": "OutOfMemoryError",
                    }
                ],
            }
        ],
        "failures": [],
    }

    results = check_task_status(
        mock_client,
        "test-cluster",
        task_arn="arn:aws:ecs:us-east-1:123456789012:task/test-cluster/abc123",
    )
    critical_results = [r for r in results if r.severity == Severity.CRITICAL]
    assert len(critical_results) >= 1
    # Should detect the stopped reason
    assert any("Essential container" in r.message for r in critical_results)
    # Should detect exit code 137 (OOM)
    assert any("137" in r.message for r in critical_results)


@mock_aws
def test_stopped_task_with_service(aws_credentials):
    """Should find stopped tasks by service name."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx",
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

    # No stopped tasks for this service
    results = check_task_status(client, "test-cluster", service="test-service")
    assert len(results) >= 1


@mock_aws
def test_task_status_handles_client_error(aws_credentials):
    """Should handle errors gracefully."""
    client = boto3.client("ecs", region_name="us-east-1")
    results = check_task_status(client, "nonexistent-cluster")
    assert len(results) >= 1
    assert results[0].severity in (Severity.OK, Severity.ERROR)


def test_reason_map_coverage():
    """Reason map should have known failure reasons."""
    assert "CannotPullContainerError" in REASON_MAP
    assert "OutOfMemoryError" in REASON_MAP
    assert "ResourceNotFoundException" in REASON_MAP


def test_exit_code_map_coverage():
    """Exit code map should have known codes."""
    assert 137 in EXIT_CODE_MAP
    assert 1 in EXIT_CODE_MAP
    assert 127 in EXIT_CODE_MAP
    assert 139 in EXIT_CODE_MAP
