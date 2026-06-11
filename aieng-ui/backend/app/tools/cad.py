"""CAD/geometry runtime tool registrations.

Reserved for the runtime-registry split proof-of-concept. Currently a stub;
CAD tools remain in ``runtime_tool_registry.py`` until the next migration slice.
"""

from __future__ import annotations

from typing import Any


def register_cad_tools(_rt: Any, _active_settings: Any, _app_context: Any, _schema: Any) -> None:
    """Register CAD/geometry runtime tools.

    TODO: migrate cad.* tool registrations from runtime_tool_registry.py.
    """
