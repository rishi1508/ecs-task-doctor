"""Tests for service_events check module."""

from __future__ import annotations

import boto3
from moto import mock_aws

from ecs_doctor.checks.service_events import _detect_crash_loop, check_service_events
from ecs_doctor.models import Severity


@mock_aws
def test_no_service_specified(aws_credentials):
    """Should skip if no service is specified."""
    client = boto3.client("ecs", region_name="us-east-1")
    results = check_service_events(client, "test-cluster", service=None)
    assert len(results) == 1
    assert results[0].severity == Severity.OK
    assert "Skipped" in results[0].message


@mock_aws
def test_service_not_found(aws_credentials):
    """Should return error if service doesn't exist."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")
    results = check_service_events(client, "test-cluster", service="nonexistent")
    assert len(results) == 1
    assert results[0].severity == Severity.ERROR


@mock_aws
def test_healthy_service_events(aws_credentials):
    """A service with no error patterns should be OK."""
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

    results = check_service_events(client, "test-cluster", service="test-service")
    # Should get at least one result
    assert len(results) >= 1


def test_detect_crash_loop_with_many_stops():
    """Should detect crash loop when many stops happen recently."""
    from datetime import datetime, timezone

    events = [
        {"message": "has stopped 1 running tasks", "createdAt": datetime.now(timezone.utc)}
        for _ in range(5)
    ]
    result = _detect_crash_loop(events)
    assert result is not None
    assert result.severity == Severity.CRITICAL
    assert "Crash loop" in result.message


def test_detect_crash_loop_no_stops():
    """No crash loop if no stop events."""
    from datetime import datetime, timezone

    events = [{"message": "has reached a steady state", "createdAt": datetime.now(timezone.utc)}]
    result = _detect_crash_loop(events)
    assert result is None
