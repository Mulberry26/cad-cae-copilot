"""Project/package runtime tool registrations.

Reserved for the runtime-registry split proof-of-concept. Currently a stub;
remaining aieng/postprocess/mcp tool registrations stay in
``runtime_tool_registry.py`` until the next migration slice.
"""

from __future__ import annotations

from typing import Any


def register_project_tools(_rt: Any, _active_settings: Any, _app_context: Any, _schema: Any) -> None:
    """Register project/package runtime tools.

    TODO: migrate remaining aieng/postprocess/mcp tool registrations from
    runtime_tool_registry.py.
    """
