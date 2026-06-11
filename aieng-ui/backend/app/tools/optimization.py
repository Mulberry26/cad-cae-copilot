"""Optimization runtime tool registrations.

Reserved for the runtime-registry split proof-of-concept. Currently a stub;
optimization tools remain in ``runtime_tool_registry.py`` until the next
migration slice.
"""

from __future__ import annotations

from typing import Any


def register_opt_tools(_rt: Any, _active_settings: Any, _app_context: Any, _schema: Any) -> None:
    """Register optimization runtime tools.

    TODO: migrate opt.* tool registrations from runtime_tool_registry.py.
    """
