"""AWS client helpers with error handling."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def get_client(service: str, region: str | None = None) -> Any:
    """Get a boto3 client for the given service.

    Args:
        service: AWS service name (e.g. 'ecs', 'logs').
        region: Optional AWS region override.

    Returns:
        A boto3 client instance.
    """
    kwargs: dict[str, Any] = {}
    if region:
        kwargs["region_name"] = region
    return boto3.client(service, **kwargs)


def handle_aws_error(err: ClientError) -> str:
    """Extract a human-readable message from a ClientError.

    Args:
        err: The botocore ClientError.

    Returns:
        A formatted error message string.
    """
    code = err.response["Error"].get("Code", "Unknown")
    message = err.response["Error"].get("Message", str(err))
    return f"AWS {code}: {message}"


def safe_aws_call(func: Any, *args: Any, **kwargs: Any) -> tuple[bool, Any]:
    """Safely call an AWS API and return (success, result_or_error).

    Args:
        func: The boto3 method to call.
        *args: Positional arguments to pass.
        **kwargs: Keyword arguments to pass.

    Returns:
        Tuple of (success: bool, result_or_error_message).
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except ClientError as e:
        return False, handle_aws_error(e)
    except BotoCoreError as e:
        return False, f"AWS error: {e}"
