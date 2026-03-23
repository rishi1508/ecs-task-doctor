"""Tests for logs check module."""

from __future__ import annotations

import time
from unittest.mock import patch

import boto3
from moto import mock_aws

from ecs_doctor.checks.logs import ERROR_PATTERNS, check_logs
from ecs_doctor.models import Severity


@mock_aws
def test_no_log_config(aws_credentials):
    """Should warn when no log config can be found."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    results = check_logs(client, "test-cluster", service="nonexistent")
    assert len(results) >= 1
    assert results[0].severity == Severity.WARNING


@mock_aws
def test_non_awslogs_driver(aws_credentials):
    """Should skip gracefully for non-awslogs drivers."""
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
                "logConfiguration": {
                    "logDriver": "json-file",
                },
            }
        ],
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_logs(client, "test-cluster", service="test-service")
    assert any("json-file" in r.message for r in results)


@mock_aws
def test_log_group_not_found(aws_credentials):
    """Should warn when the log group doesn't exist."""
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
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/nonexistent",
                        "awslogs-region": "us-east-1",
                        "awslogs-stream-prefix": "ecs",
                    },
                },
            }
        ],
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_logs(client, "test-cluster", service="test-service")
    assert len(results) >= 1


@mock_aws
def test_logs_with_error_patterns(aws_credentials):
    """Should detect error patterns in log messages."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    logs_client = boto3.client("logs", region_name="us-east-1")

    ecs_client.create_cluster(clusterName="test-cluster")

    ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx",
                "cpu": 256,
                "memory": 512,
                "essential": True,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/test-task",
                        "awslogs-region": "us-east-1",
                        "awslogs-stream-prefix": "ecs",
                    },
                },
            }
        ],
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    # Create log group and stream with error messages
    logs_client.create_log_group(logGroupName="/ecs/test-task")
    logs_client.create_log_stream(logGroupName="/ecs/test-task", logStreamName="ecs/app/abc123")
    logs_client.put_log_events(
        logGroupName="/ecs/test-task",
        logStreamName="ecs/app/abc123",
        logEvents=[
            {"timestamp": int(time.time() * 1000), "message": "FATAL: out of memory"},
            {
                "timestamp": int(time.time() * 1000) + 1,
                "message": "Error: connection refused to database:5432",
            },
        ],
    )

    # Patch get_client so check_logs uses the already-mocked logs client
    with patch("ecs_doctor.checks.logs.get_client", return_value=logs_client):
        results = check_logs(ecs_client, "test-cluster", service="test-service")

    critical = [r for r in results if r.severity == Severity.CRITICAL]
    assert len(critical) >= 1


@mock_aws
def test_logs_clean(aws_credentials):
    """Should report OK when no error patterns in logs."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    logs_client = boto3.client("logs", region_name="us-east-1")

    ecs_client.create_cluster(clusterName="test-cluster")

    ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx",
                "cpu": 256,
                "memory": 512,
                "essential": True,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": "/ecs/test-task",
                        "awslogs-region": "us-east-1",
                        "awslogs-stream-prefix": "ecs",
                    },
                },
            }
        ],
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    logs_client.create_log_group(logGroupName="/ecs/test-task")
    logs_client.create_log_stream(logGroupName="/ecs/test-task", logStreamName="ecs/app/abc123")
    logs_client.put_log_events(
        logGroupName="/ecs/test-task",
        logStreamName="ecs/app/abc123",
        logEvents=[
            {"timestamp": int(time.time() * 1000), "message": "Server started on port 8080"},
            {
                "timestamp": int(time.time() * 1000) + 1,
                "message": "Health check passed",
            },
        ],
    )

    with patch("ecs_doctor.checks.logs.get_client", return_value=logs_client):
        results = check_logs(ecs_client, "test-cluster", service="test-service")

    ok_results = [r for r in results if r.severity == Severity.OK]
    assert len(ok_results) >= 1


def test_error_patterns_exist():
    """Should have known error patterns defined."""
    patterns = [p[1] for p in ERROR_PATTERNS]
    assert any("memory" in p.lower() for p in patterns)
    assert any("connection" in p.lower() for p in patterns)
    assert any("permission" in p.lower() for p in patterns)
