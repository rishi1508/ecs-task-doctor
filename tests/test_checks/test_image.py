"""Tests for image check module."""

from __future__ import annotations

from unittest.mock import patch

import boto3
from moto import mock_aws

from ecs_doctor.checks.image import _parse_ecr_uri, check_image
from ecs_doctor.models import Severity


def test_parse_ecr_uri_valid():
    """Should parse a valid ECR URI."""
    uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.0"
    parsed = _parse_ecr_uri(uri)
    assert parsed is not None
    assert parsed["account"] == "123456789012"
    assert parsed["region"] == "us-east-1"
    assert parsed["repo"] == "myapp"
    assert parsed["tag"] == "v1.0"


def test_parse_ecr_uri_no_tag():
    """Should default to 'latest' when no tag is specified."""
    uri = "123456789012.dkr.ecr.us-west-2.amazonaws.com/myapp"
    parsed = _parse_ecr_uri(uri)
    assert parsed is not None
    assert parsed["tag"] == "latest"


def test_parse_ecr_uri_non_ecr():
    """Should return None for non-ECR images."""
    assert _parse_ecr_uri("nginx:latest") is None
    assert _parse_ecr_uri("docker.io/library/nginx") is None


def test_parse_ecr_uri_with_digest():
    """Should parse URIs with digests."""
    uri = "123456789012.dkr.ecr.us-east-1.amazonaws.com/myapp@sha256:abc123"
    parsed = _parse_ecr_uri(uri)
    assert parsed is not None
    assert parsed["digest"] == "sha256:abc123"


@mock_aws
def test_no_images_found(aws_credentials):
    """Should warn when no images can be determined."""
    client = boto3.client("ecs", region_name="us-east-1")
    client.create_cluster(clusterName="test-cluster")

    results = check_image(client, "test-cluster", service="nonexistent")
    assert len(results) >= 1
    assert results[0].severity == Severity.WARNING


@mock_aws
def test_non_ecr_image_skipped(aws_credentials):
    """Should skip non-ECR images gracefully."""
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

    results = check_image(client, "test-cluster", service="test-service")
    assert any("not an ECR image" in r.message for r in results)


@mock_aws
def test_ecr_image_exists(aws_credentials):
    """Should verify an existing ECR image."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    ecr_client = boto3.client("ecr", region_name="us-east-1")

    ecs_client.create_cluster(clusterName="test-cluster")

    # Create ECR repository and put image
    ecr_client.create_repository(repositoryName="myapp")
    ecr_client.put_image(
        repositoryName="myapp",
        imageManifest=(
            '{"schemaVersion": 2, "mediaType":'
            ' "application/vnd.docker.distribution.manifest.v2+json"}'
        ),
        imageManifestMediaType="application/vnd.docker.distribution.manifest.v2+json",
        imageTag="v1.0",
    )

    # Get the account ID from STS
    sts_client = boto3.client("sts", region_name="us-east-1")
    account_id = sts_client.get_caller_identity()["Account"]

    ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": f"{account_id}.dkr.ecr.us-east-1.amazonaws.com/myapp:v1.0",
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

    # Patch get_client so the image check uses the mocked ECR client
    with patch("ecs_doctor.checks.image.get_client", return_value=ecr_client):
        results = check_image(ecs_client, "test-cluster", service="test-service")

    ok_results = [r for r in results if r.severity == Severity.OK]
    assert len(ok_results) >= 1
    assert any("exists" in r.message for r in ok_results)


@mock_aws
def test_ecr_repo_not_found(aws_credentials):
    """Should flag missing ECR repository."""
    ecs_client = boto3.client("ecs", region_name="us-east-1")
    ecr_client = boto3.client("ecr", region_name="us-east-1")
    sts_client = boto3.client("sts", region_name="us-east-1")
    account_id = sts_client.get_caller_identity()["Account"]

    ecs_client.create_cluster(clusterName="test-cluster")

    ecs_client.register_task_definition(
        family="test-task",
        containerDefinitions=[
            {
                "name": "app",
                "image": f"{account_id}.dkr.ecr.us-east-1.amazonaws.com/nonexistent:v1.0",
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

    with patch("ecs_doctor.checks.image.get_client", return_value=ecr_client):
        results = check_image(ecs_client, "test-cluster", service="test-service")

    critical = [r for r in results if r.severity == Severity.CRITICAL]
    assert len(critical) >= 1
