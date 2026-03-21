"""Shared test fixtures for ECS Task Doctor."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def aws_credentials(monkeypatch):
    """Set dummy AWS credentials for moto."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def mock_aws_env(aws_credentials):
    """Start moto mock for all AWS services."""
    with mock_aws():
        yield


@pytest.fixture
def ecs_client(mock_aws_env):
    """Create a mocked ECS client."""
    return boto3.client("ecs", region_name="us-east-1")


@pytest.fixture
def ec2_client(mock_aws_env):
    """Create a mocked EC2 client."""
    return boto3.client("ec2", region_name="us-east-1")


@pytest.fixture
def iam_client(mock_aws_env):
    """Create a mocked IAM client."""
    return boto3.client("iam", region_name="us-east-1")


@pytest.fixture
def logs_client(mock_aws_env):
    """Create a mocked CloudWatch Logs client."""
    return boto3.client("logs", region_name="us-east-1")


@pytest.fixture
def ecr_client(mock_aws_env):
    """Create a mocked ECR client."""
    return boto3.client("ecr", region_name="us-east-1")


@pytest.fixture
def setup_cluster(ecs_client):
    """Create a basic ECS cluster with a service and task definition."""
    # Create cluster
    ecs_client.create_cluster(clusterName="test-cluster")

    # Register a task definition
    ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:latest",
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
        executionRoleArn="arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
        taskRoleArn="arn:aws:iam::123456789012:role/ecsTaskRole",
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
    )

    # Create service
    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=2,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": ["subnet-12345"],
                "securityGroups": ["sg-12345"],
            }
        },
    )

    return ecs_client
