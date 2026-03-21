# ECS Task Doctor

[![CI](https://github.com/rishi1508/ecs-task-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/rishi1508/ecs-task-doctor/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/ecs-task-doctor.svg)](https://pypi.org/project/ecs-task-doctor/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Diagnose why your ECS tasks fail to start or keep crashing — in one command.**

ECS Task Doctor aggregates information from ECS, CloudWatch, ECR, IAM, and EC2 into a single, human-readable diagnosis report. No more jumping between 7 AWS console tabs.

<!-- screenshot placeholder -->
<!-- ![ECS Task Doctor Screenshot](docs/screenshot.png) -->

## Installation

```bash
pip install ecs-task-doctor
```

## Quick Start

```bash
# Diagnose a specific service
ecs-doctor diagnose --cluster my-cluster --service my-service

# Diagnose a specific task
ecs-doctor diagnose --cluster my-cluster --task arn:aws:ecs:us-east-1:123:task/my-cluster/abc123

# Scan all services in a cluster for issues
ecs-doctor scan --cluster my-cluster

# Quick health check
ecs-doctor health --cluster my-cluster
```

## What It Checks

| Check | What it does |
|-------|-------------|
| **Task Status** | Parses stopped reasons and container exit codes (OOM, segfault, etc.) |
| **Service Events** | Detects crash loops, placement failures, and capacity issues |
| **CloudWatch Logs** | Scans recent logs for error patterns (OOM, connection refused, etc.) |
| **Image** | Verifies ECR images exist and are pullable |
| **IAM** | Validates task execution and task roles exist |
| **Resources** | Checks CPU/memory constraints and cluster capacity |
| **Networking** | Verifies subnets have IPs, security groups allow egress |

## Example Output

```
╭─────────────────────────────────────────────────╮
│  ECS Task Doctor — Diagnosis Report             │
│  Cluster: production  Service: api-server       │
╰─────────────────────────────────────────────────╯

🔴 CRITICAL: Container keeps crashing (3 restarts in 10 min)

📋 Checks:
  ✅ Image: 123456789.dkr.ecr.us-east-1.amazonaws.com/api:v2.1.0 — exists and pullable
  ✅ IAM: Task execution role has required permissions
  ✅ Network: Subnets have available IPs, security groups allow egress
  ❌ Task Status: Essential container exited with code 137 (OOM Kill)
  ⚠️  Resources: Container memory limit (512MB) is close to task memory (512MB)
  ❌ Logs: Last error — "JavaScript heap out of memory"

💡 Recommendation:
  1. Increase container memory limit from 512MB to 1024MB
  2. Update task definition memory from 512 to 1024
  3. Consider adding --max-old-space-size=768 to Node.js startup

📝 Full logs: aws logs tail /ecs/api-server --since 1h
```

## Output Formats

```bash
# Rich terminal output (default)
ecs-doctor diagnose --cluster my-cluster --service my-service

# JSON (for scripting/automation)
ecs-doctor diagnose --cluster my-cluster --service my-service --format json

# Markdown (for reports/PRs)
ecs-doctor diagnose --cluster my-cluster --service my-service --format markdown
```

## Commands

### `ecs-doctor diagnose`

Run a full diagnosis on a service or task.

```bash
ecs-doctor diagnose --cluster CLUSTER --service SERVICE [--region REGION] [--format FORMAT]
ecs-doctor diagnose --cluster CLUSTER --task TASK_ARN [--region REGION] [--format FORMAT]
```

### `ecs-doctor scan`

Scan all services in a cluster and diagnose any unhealthy ones.

```bash
ecs-doctor scan --cluster CLUSTER [--region REGION] [--format FORMAT]
```

### `ecs-doctor health`

Quick health overview of all services in a cluster.

```bash
ecs-doctor health --cluster CLUSTER [--region REGION] [--format FORMAT]
```

## Required AWS Permissions

ECS Task Doctor needs read-only access to several AWS services:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:DescribeClusters",
        "ecs:DescribeServices",
        "ecs:DescribeTasks",
        "ecs:DescribeTaskDefinition",
        "ecs:ListServices",
        "ecs:ListTasks",
        "ecs:ListContainerInstances",
        "ecs:DescribeContainerInstances",
        "logs:DescribeLogStreams",
        "logs:GetLogEvents",
        "ecr:DescribeRepositories",
        "ecr:DescribeImages",
        "iam:GetRole",
        "ec2:DescribeSubnets",
        "ec2:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

## Development

```bash
# Install in dev mode
pip install -e '.[dev]'

# Run tests
pytest -v

# Lint
ruff check src/ tests/
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## License

MIT — see [LICENSE](LICENSE).
