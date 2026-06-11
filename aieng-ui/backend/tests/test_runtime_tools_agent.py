"""Tests for the runtime registry split: agent/onboarding tools.

These tests verify that ``app.tools.agent.register_agent_tools`` correctly
registers the agent/onboarding tools that were extracted from
``runtime_tool_registry.py`` for the split proof-of-concept.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.runtime_tool_schemas import get_schema
from app.tools import agent as _agent_tools


class _MockAppContext:
    delete_project_everywhere = MagicMock(return_value={"deleted": True})


def test_register_agent_tools_registers_expected_tools() -> None:
    """All agent/onboarding tools are registered with correct metadata."""
    registered: dict[str, dict[str, Any]] = {}

    def _register_tool(name: str, handler: Any, **kwargs: Any) -> None:
        registered[name] = {"handler": handler, **kwargs}

    mock_rt = MagicMock()
    mock_rt.register_tool = _register_tool
    mock_rt.registry_identity = MagicMock(return_value={"tool_count": 0, "registry_hash": "sha256:probe"})

    active_settings = MagicMock()
    active_settings.projects_root = MagicMock()
    active_settings.projects_root.glob = MagicMock(return_value=[])

    _agent_tools.register_agent_tools(
        rt=mock_rt,
        active_settings=active_settings,
        app_context=_MockAppContext(),
        _schema=get_schema,
    )

    expected = {
        "aieng.list_projects",
        "aieng.create_project",
        "aieng.find_projects_by_part",
        "aieng.delete_project",
        "aieng.agent_readme",
        "aieng.guide",
        "aieng.inspect_package",
        "aieng.agent_context",
    }
    assert expected.issubset(set(registered.keys()))
    assert registered["aieng.delete_project"].get("requires_approval") is True
    assert registered["aieng.list_projects"].get("input_schema") is not None
    assert registered["aieng.agent_readme"].get("input_schema") is not None


def test_register_agent_tools_registry_identity_probe() -> None:
    """aieng.agent_readme embeds the registry identity from the runtime."""
    registered: dict[str, dict[str, Any]] = {}

    def _register_tool(name: str, handler: Any, **kwargs: Any) -> None:
        registered[name] = {"handler": handler, **kwargs}

    mock_rt = MagicMock()
    mock_rt.register_tool = _register_tool
    mock_rt.registry_identity = MagicMock(return_value={"tool_count": 42, "registry_hash": "sha256:agent"})

    active_settings = MagicMock()
    active_settings.projects_root = MagicMock()
    active_settings.projects_root.glob = MagicMock(return_value=[])

    _agent_tools.register_agent_tools(
        rt=mock_rt,
        active_settings=active_settings,
        app_context=_MockAppContext(),
        _schema=get_schema,
    )

    handler = registered["aieng.agent_readme"]["handler"]
    result = handler({}, {})
    assert result["registry"] == {"tool_count": 42, "registry_hash": "sha256:agent"}
    mock_rt.registry_identity.assert_called_once_with()
