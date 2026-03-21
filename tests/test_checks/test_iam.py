"""Tests for IAM check module."""

from __future__ import annotations

import json

import boto3
from moto import mock_aws

from ecs_doctor.checks.iam import _extract_role_name, check_iam
from ecs_doctor.models import Severity


def test_extract_role_name_from_arn():
    """Should extract role name from ARN."""
    assert _extract_role_name("arn:aws:iam::123456789012:role/myRole") == "myRole"
    assert _extract_role_name("arn:aws:iam::123456789012:role/path/myRole") == "myRole"


def test_extract_role_name_plain():
    """Should return plain name as-is."""
    assert _extract_role_name("myRole") == "myRole"


@mock_aws
def test_no_task_def(aws_credentials):
    """Should warn when task def can't be found."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    results = check_iam(client, "test-cluster", service="nonexistent")
    assert len(results) >= 1
    assert results[0].severity == Severity.WARNING


@mock_aws
def test_execution_role_exists(aws_credentials):
    """Should report OK when execution role exists."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    iam_client = boto3.client("iam", region_name="us-east-1")

    ecs_client.create_cluster(clusterName="test-cluster")

    # Create the IAM role
    iam_client.create_role(
        RoleName="ecsTaskExecutionRole",
        AssumeRolePolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }),
    )

    ecs_client.register_task_definition(
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
        executionRoleArn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_iam(ecs_client, "test-cluster", service="test-service")
    ok_results = [r for r in results if r.severity == Severity.OK]
    assert len(ok_results) >= 1
    assert any("execution role" in r.message for r in ok_results)


@mock_aws
def test_missing_execution_role(aws_credentials):
    """Should flag when execution role doesn't exist."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
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
            }
        ],
        executionRoleArn="arn:aws:iam::123456789012:role/nonexistentRole",
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_iam(ecs_client, "test-cluster", service="test-service")
    critical = [r for r in results if r.severity == Severity.CRITICAL]
    assert len(critical) >= 1


@mock_aws
def test_no_execution_role_defined(aws_credentials):
    """Should warn when no execution role is defined."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
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
            }
        ],
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_iam(ecs_client, "test-cluster", service="test-service")
    warnings = [r for r in results if r.severity == Severity.WARNING]
    assert len(warnings) >= 1
    assert any("No execution role" in r.message for r in warnings)


@mock_aws
def test_secrets_warning(aws_credentials):
    """Should warn about secrets permissions."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
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
                "secrets": [
                    {
                        "name": "DB_PASSWORD",
                        "valueFrom": "arn:aws:secretsmanager:us-east-1:123:secret:db-pass",
                    }
                ],
            }
        ],
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_iam(ecs_client, "test-cluster", service="test-service")
    warnings = [r for r in results if r.severity == Severity.WARNING]
    assert any("secrets" in r.message.lower() for r in warnings)
