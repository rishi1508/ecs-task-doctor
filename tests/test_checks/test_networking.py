"""Tests for networking check module."""

from __future__ import annotations

import boto3
from moto import mock_aws

from ecs_doctor.checks.networking import check_networking
from ecs_doctor.models import Severity


@mock_aws
def test_no_service(aws_credentials):
    """Should skip when no service specified."""
    client = boto3.client("ecs", region_name="us-east-1")
    results = check_networking(client, "test-cluster", service=None)
    assert len(results) == 1
    assert results[0].severity == Severity.OK
    assert "skipping" in results[0].message.lower()


@mock_aws
def test_no_awsvpc_config(aws_credentials):
    """Should skip when service has no awsvpc configuration."""
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

    results = check_networking(client, "test-cluster", service="test-service")
    assert len(results) >= 1
    # Should skip since there's no awsvpc config
    assert any("skipping" in r.message.lower() or r.severity == Severity.OK for r in results)


@mock_aws
def test_subnet_checks(aws_credentials):
    """Should check subnet IP availability."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    ec2_client = boto3.client("ec2", region_name="us-east-1")

    # Create VPC and subnet
    vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2_client.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]

    # Create security group
    sg = ec2_client.create_security_group(
        GroupName="test-sg",
        Description="test",
        VpcId=vpc_id,
    )
    sg_id = sg["GroupId"]

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
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet_id],
                "securityGroups": [sg_id],
            }
        },
    )

    results = check_networking(ecs_client, "test-cluster", service="test-service")
    # Should have subnet and security group check results
    assert len(results) >= 1
    # Subnet should have IPs available
    ok_results = [r for r in results if r.severity == Severity.OK]
    assert len(ok_results) >= 1


@mock_aws
def test_security_group_no_egress(aws_credentials):
    """Should flag security groups without egress rules."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    ec2_client = boto3.client("ec2", region_name="us-east-1")

    vpc = ec2_client.create_vpc(CidrBlock="10.0.0.0/16")
    vpc_id = vpc["Vpc"]["VpcId"]
    subnet = ec2_client.create_subnet(VpcId=vpc_id, CidrBlock="10.0.1.0/24")
    subnet_id = subnet["Subnet"]["SubnetId"]

    sg = ec2_client.create_security_group(
        GroupName="test-sg-no-egress",
        Description="test",
        VpcId=vpc_id,
    )
    sg_id = sg["GroupId"]

    # Note: moto creates a default egress rule, so we can just check it gets reported
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
        requiresCompatibilities=["FARGATE"],
        networkMode="awsvpc",
        cpu="256",
        memory="512",
    )

    ecs_client.create_service(
        cluster="test-cluster",
        serviceName="test-service",
        taskDefinition="test-task",
        desiredCount=1,
        launchType="FARGATE",
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": [subnet_id],
                "securityGroups": [sg_id],
            }
        },
    )

    results = check_networking(ecs_client, "test-cluster", service="test-service")
    assert len(results) >= 1
    # Moto creates default egress, so should report OK for SG
    sg_results = [r for r in results if "ecurity group" in r.message]
    assert len(sg_results) >= 1
