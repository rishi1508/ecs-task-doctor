# Contributing to ECS Task Doctor

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/ecs-task-doctor.git
   cd ecs-task-doctor
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install in development mode:
   ```bash
   pip install -e '.[dev]'
   ```

## Running Tests

```bash
pytest -v
```

All AWS calls are mocked using [moto](https://github.com/getmoto/moto) — no real AWS credentials needed.

## Code Style

We use [ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Adding a New Check Module

1. Create a new file in `src/ecs_doctor/checks/`
2. Implement the check function with this signature:
   ```python
   def check_your_check(
       ecs_client: Any,
       cluster: str,
       service: Optional[str] = None,
       task_arn: Optional[str] = None,
   ) -> list[CheckResult]:
   ```
3. Add it to `ALL_CHECKS` in `src/ecs_doctor/checks/__init__.py`
4. Write tests in `tests/test_checks/test_your_check.py`

## Pull Requests

- Create a branch from `main`
- Write tests for new functionality
- Ensure all tests pass (`pytest -v`)
- Ensure code passes linting (`ruff check`)
- Keep PRs focused on a single change
- Write a clear description of what your change does and why

## Reporting Issues

Please include:
- The command you ran
- Expected vs actual behavior
- Your Python version and OS
- Any relevant error output
