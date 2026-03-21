"""Output formatters for diagnosis reports."""

from ecs_doctor.formatters.console import format_console
from ecs_doctor.formatters.json_fmt import format_json
from ecs_doctor.formatters.markdown import format_markdown

__all__ = ["format_console", "format_json", "format_markdown"]
