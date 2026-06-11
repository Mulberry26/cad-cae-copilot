"""Tests for extracted runtime tool registrations.

Verifies that engineering_template.* and freecad.* wrapper tools are still
registered with the same approval semantics after the move from app_factory.py
to runtime_tools.py.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.app_factory import create_app
from app.config import Settings

_WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _make_settings(tmp_path: Path) -> Settings:
    workspace = tmp_path / "workspace"
    return Settings(
        platform_root=tmp_path / "platform",
        workspace_root=workspace,
        data_root=tmp_path / "data",
        aieng_root=_WORKSPACE_ROOT / "aieng",
        sample_step=workspace / "sample.step",
    )


def _make_project(settings: Settings, name: str, package: str) -> tuple[str, Path]:
    from app.main import default_project, project_dir, save_project

    project = save_project(settings, default_project(name))
    project_id = project["id"]
    pkg_path = project_dir(settings, project_id) / package
    project["aieng_file"] = package
    save_project(settings, project)
    return project_id, pkg_path


def _make_minimal_package(pkg: Path, *, extra_members: dict[str, bytes] | None = None) -> None:
    pkg.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pkg, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({"model_id": "rt-test", "resources": {}}))
        for path, payload in (extra_members or {}).items():
            zf.writestr(path, payload)


_DEFAULT_SNAPSHOT: dict[str, Any] = {
    "source": "freecad_mcp",
    "captured_at": "2026-05-20T12:00:00Z",
    "document_name": "test",
    "generator": "test-suite",
    "object_count": 1,
    "objects": [],
    "named_regions": [],
    "topology_references": {},
    "warnings": [],
}


# ── registration smoke tests ────────────────────────────────────────────────


def test_engineering_template_tools_are_registered(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    client = TestClient(create_app(settings))
    tools = {t["name"]: t for t in client.get("/api/runtime/tools").json()}

    assert "engineering_template.preview" in tools
    assert tools["engineering_template.preview"]["requires_approval"] is False

    assert "engineering_template.save_draft" in tools
    assert tools["engineering_template.save_draft"]["requires_approval"] is True

    assert "engineering_template.adopt_targets" in tools
    assert tools["engineering_template.adopt_targets"]["requires_approval"] is True

    assert "engineering_template.generate_cad_fixture" in tools
    assert tools["engineering_template.generate_cad_fixture"]["requires_approval"] is True


def test_engineering_template_preview_is_read_only(tmp_path: Path) -> None:
    """Read-only engineering template tool should execute without approval."""
    settings = _make_settings(tmp_path)
    client = TestClient(create_app(settings))
    project_id, pkg = _make_project(settings, "rt-preview", "p.aieng")
    _make_minimal_package(pkg)

    run = client.post(
        "/api/runtime/runs",
        json={
            "project_id": project_id,
            "steps": [
                {
                    "id": "preview1",
                    "tool_name": "engineering_template.preview",
                    "name": "engineering_template.preview",
                    "input": {"project_id": project_id, "template_id": "cantilever_beam"},
                    "approval_required": False,
                    "status": "pending",
                }
            ],
        },
    )
    assert run.status_code == 200, run.text
    run_dict = run.json()
    assert run_dict["status"] == "completed"


# ── migrated CAD tool registration smoke tests ────────────────────────────────


_CAD_TOOLS_EXPECTED: dict[str, dict[str, Any]] = {
    # read-only / no-approval tools
    "cad.plan_build123d_skill": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.get_source": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.list_editable_parameters": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.critique": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.design_review": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.get_named_part_bbox": {"requires_approval": False, "read_only": True, "destructive": False},
    "cad.list_snapshots": {"requires_approval": False, "read_only": True, "destructive": False},
    # package-mutating but per-call approval=false (plan-level gating)
    "cad.execute_build123d": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.set_reference_image": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.search_reference_image": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.refine": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.edit_parameter": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.remove_part": {"requires_approval": False, "read_only": False, "destructive": False},
    "cad.replace_part": {"requires_approval": False, "read_only": False, "destructive": False},
    # approval-gated tools
    "cad.confirm_modeling_plan": {"requires_approval": True, "read_only": False, "destructive": True},
    "cad.restore_snapshot": {"requires_approval": True, "read_only": False, "destructive": True},
}


def test_cad_tools_are_registered_after_migration(tmp_path: Path) -> None:
    """All cad.* tools survive the move from runtime_tool_registry.py."""
    settings = _make_settings(tmp_path)
    client = TestClient(create_app(settings))
    tools = {t["name"]: t for t in client.get("/api/runtime/tools").json()}

    for name, expected in _CAD_TOOLS_EXPECTED.items():
        assert name in tools, f"{name} not registered after migration"
        actual = tools[name]
        for key, value in expected.items():
            assert actual[key] == value, f"{name}.{key} = {actual[key]!r}, expected {value!r}"


def test_register_cad_tools_directly() -> None:
    """The new registrar can be called with a minimal registry stand-in."""
    from app import runtime_cad_tools

    registered: dict[str, dict[str, Any]] = {}

    class _FakeRegistry:
        @staticmethod
        def register_tool(name: str, handler: Any, **kwargs: Any) -> None:
            registered[name] = {"handler": handler, **kwargs}

    runtime_cad_tools.register_cad_tools(
        _FakeRegistry(),
        active_settings=None,
        load_project_feature_parameters=lambda _pid: None,
    )

    assert set(registered) == set(_CAD_TOOLS_EXPECTED)
    for name in _CAD_TOOLS_EXPECTED:
        assert registered[name]["handler"] is not None
        assert registered[name].get("description")
        # Approval-gated tools must explicitly pass requires_approval=True.
        if name in {"cad.confirm_modeling_plan", "cad.restore_snapshot"}:
            assert registered[name].get("requires_approval") is True
