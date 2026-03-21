"""Diagnostic check modules."""

from ecs_doctor.checks.iam import check_iam
from ecs_doctor.checks.image import check_image
from ecs_doctor.checks.logs import check_logs
from ecs_doctor.checks.networking import check_networking
from ecs_doctor.checks.resources import check_resources
from ecs_doctor.checks.service_events import check_service_events
from ecs_doctor.checks.task_status import check_task_status

ALL_CHECKS = [
    check_task_status,
    check_service_events,
    check_logs,
    check_image,
    check_iam,
    check_resources,
    check_networking,
]

__all__ = [
    "ALL_CHECKS",
    "check_iam",
    "check_image",
    "check_logs",
    "check_networking",
    "check_resources",
    "check_service_events",
    "check_task_status",
]
