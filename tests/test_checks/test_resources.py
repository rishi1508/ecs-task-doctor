"""Tests for resources check module."""

from __future__ import annotations

import boto3
from moto import mock_aws

from ecs_doctor.checks.resources import check_resources
from ecs_doctor.models import Severity


@mock_aws
def test_no_task_def(aws_credentials):
    """Should warn when task def can't be found."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    results = check_resources(client, "test-cluster", service="nonexistent")
    assert len(results) >= 1
    assert results[0].severity == Severity.WARNING


@mock_aws
def test_fargate_resources(aws_credentials):
    """Should check Fargate resource configuration."""
    client = boto3.client("ecs", region_name="us-east-1")
    ec2 = boto3.client("ec2", region_name="us-east-1")

    client.create_cluster(clusterName="test-cluster")

    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2.create_subnet(VpcId=vpc["Vpc"]["VpcId"], CidrBlock="10.0.1.0/24")
    sg = ec2.create_security_group(
        GroupName="test-sg", Description="test", VpcId=vpc["Vpc"]["VpcId"]
    )

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
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet["Subnet"]["SubnetId"]],
                "securityGroups": [sg["GroupId"]],
            }
        },
    )

    results = check_resources(client, "test-cluster", service="test-service")
    assert len(results) >= 1


@mock_aws
def test_container_memory_at_limit(aws_credentials):
    """Should warn when container memory equals task memory."""
    client = boto3.client("ecs", region_name="us-east-1")
    ec2 = boto3.client("ec2", region_name="us-east-1")

    client.create_cluster(clusterName="test-cluster")

    vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2.create_subnet(VpcId=vpc["Vpc"]["VpcId"], CidrBlock="10.0.1.0/24")
    sg = ec2.create_security_group(
        GroupName="test-sg", Description="test", VpcId=vpc["Vpc"]["VpcId"]
    )

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
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet["Subnet"]["SubnetId"]],
                "securityGroups": [sg["GroupId"]],
            }
        },
    )

    results = check_resources(client, "test-cluster", service="test-service")
    warnings = [r for r in results if r.severity == Severity.WARNING]
    assert len(warnings) >= 1
    assert any("memory" in r.message.lower() for r in warnings)


@mock_aws
def test_ec2_no_container_instances(aws_credentials):
    """Should flag when EC2 cluster has no container instances."""
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
        cpu="256",
        memory="512",
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_resources(client, "test-cluster", service="test-service")
    critical = [r for r in results if r.severity == Severity.CRITICAL]
    assert len(critical) >= 1
    assert any("No active container instances" in r.message for r in critical)


@mock_aws
def test_ec2_no_memory_limit(aws_credentials):
    """Should warn when EC2 container has no memory limit."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": "nginx",
                "cpu": 256,
                "essential": True,
            }
        ],
        cpu="256",
        memory="512",
    )

    client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
    )

    results = check_resources(client, "test-cluster", service="test-service")
    warnings = [r for r in results if r.severity == Severity.WARNING]
    assert any("no memory limit" in r.message.lower() for r in warnings)
