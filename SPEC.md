# ECS Task Doctor — Project Specification

## Overview
A lightweight, zero-config CLI tool that diagnoses why ECS tasks fail to start or keep crashing. It aggregates information from multiple AWS sources (ECS, CloudWatch, EC2, IAM, ECR) into a single, human-readable diagnosis.

## Problem Statement
When an ECS task fails, engineers have to:
1. Check ECS service events
2. Check stopped task reasons
3. Check CloudWatch logs
4. Check container exit codes
5. Check IAM role permissions
6. Check ECR image availability
7. Check resource constraints (CPU/memory)

This tool does ALL of that in one command.

## Usage
```bash
# Diagnose a specific service
ecs-doctor diagnose --cluster my-cluster --service my-service

# Diagnose a specific task
ecs-doctor diagnose --cluster my-cluster --task arn:aws:ecs:...

# Diagnose all failing services in a cluster
ecs-doctor scan --cluster my-cluster

# Quick health check
ecs-doctor health --cluster my-cluster

# Output formats
ecs-doctor diagnose --cluster my-cluster --service my-service --format json
ecs-doctor diagnose --cluster my-cluster --service my-service --format markdown
```

## Technical Architecture

### Language: Python 3.9+
- Widely used in DevOps
- boto3 is the standard AWS SDK
- Easy to install via pip

### Package Structure
```
ecs-task-doctor/
├── src/
│   └── ecs_doctor/
│       ├── __init__.py
│       ├── cli.py              # Click-based CLI
│       ├── diagnose.py         # Core diagnosis engine
│       ├── checks/
│       │   ├── __init__.py
│       │   ├── task_status.py  # ECS task stopped reasons
│       │   ├── service_events.py # ECS service events analysis
│       │   ├── logs.py         # CloudWatch log analysis
│       │   ├── image.py        # ECR image checks
│       │   ├── iam.py          # IAM role/policy checks
│       │   ├── resources.py    # CPU/memory constraint checks
│       │   └── networking.py   # VPC/SG/subnet checks
│       ├── formatters/
│       │   ├── __init__.py
│       │   ├── console.py      # Rich terminal output
│       │   ├── json_fmt.py     # JSON output
│       │   └── markdown.py     # Markdown output
│       └── utils/
│           ├── __init__.py
│           └── aws.py          # AWS client helpers
├── tests/
│   ├── __init__.py
│   ├── test_diagnose.py
│   ├── test_checks/
│   │   ├── test_task_status.py
│   │   ├── test_service_events.py
│   │   └── ...
│   └── fixtures/
│       └── ...                 # Mock AWS responses
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── CONTRIBUTING.md
└── .github/
    └── workflows/
        ├── ci.yml              # Test + lint on PR
        └── publish.yml         # Publish to PyPI on release
```

### Dependencies
- `boto3` — AWS SDK
- `click` — CLI framework
- `rich` — Beautiful terminal output (tables, colors, panels)
- `pydantic` — Data models (optional)

### Dev Dependencies
- `pytest` — Testing
- `moto` — AWS mocking
- `ruff` — Linting
- `mypy` — Type checking

## Diagnosis Checks (Priority Order)

### 1. Task Status Check
- Get recently stopped tasks
- Parse `stoppedReason` field
- Map common reasons to actionable fixes:
  - "Essential container in task exited" → check container logs
  - "CannotPullContainerError" → ECR/network issue
  - "ResourceNotFoundException" → task definition deleted
  - "OutOfMemoryError" → increase memory limit

### 2. Service Events Analysis
- Get last 20 service events
- Detect patterns:
  - "has reached a steady state" → healthy
  - "unable to place a task" → capacity/constraint issue
  - "target group has no registered targets" → deployment issue
  - Rate of task starts/stops → crash loop detection

### 3. CloudWatch Log Analysis
- Find log group from task definition
- Get last 50 log lines from failed containers
- Pattern match for common errors:
  - OOM kills
  - Connection refused
  - Permission denied
  - Module not found
  - Segfaults

### 4. Image Checks
- Verify ECR image exists and is pullable
- Check image tag vs task definition
- Check ECR repository policy

### 5. IAM Checks
- Verify task execution role exists
- Verify task role exists
- Check for common missing permissions:
  - ecr:GetAuthorizationToken
  - ecr:BatchGetImage
  - logs:CreateLogStream
  - logs:PutLogEvents
  - secretsmanager:GetSecretValue (if using secrets)

### 6. Resource Checks
- Compare task CPU/memory requirements vs available capacity
- Check cluster capacity providers
- Identify if Fargate vs EC2 launch type constraints

### 7. Networking Checks (Fargate awsvpc)
- Verify subnets have available IPs
- Check security group rules
- Verify VPC endpoints or NAT gateway for ECR access

## Output Format
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

## MVP Scope (v0.1.0)
Focus on checks 1-3 first:
1. Task status + stopped reasons
2. Service events analysis
3. CloudWatch log retrieval

Then iterate to add 4-7 in subsequent versions.

## Testing Strategy
- Use `moto` to mock ALL AWS calls
- Every check module has corresponding test with fixture data
- Integration test with a full mock cluster scenario
- CI runs on every PR via GitHub Actions

## Publishing
- PyPI package: `ecs-task-doctor`
- CLI entry point: `ecs-doctor`
- GitHub releases with changelog
