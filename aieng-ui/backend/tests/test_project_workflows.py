"""Tests for project workflow read-only endpoints (geometry-report, cae-setup-overlay, etc.)."""

import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.main import Settings, create_app, default_project, project_dir, save_project

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


def _make_cae_package(pkg_path: Path, *, missing_setup: bool = False, stale_face: bool = False) -> None:
    pkg_path.parent.mkdir(parents=True, exist_ok=True)
    setup = {
        "schema_version": "0.1",
        "analysis_type": "static_structural",
        "material_name": "Al6061-T6",
        "mesh": {"target_size_mm": 2.5},
        "topology_hash": "abc123",
        "loads": [
            {
                "id": "load_001",
                "target_feature": "base",
                "target_face_ids": ["face_002"],
                "type": "force",
                "value_n": 500.0,
                "direction": [0.0, 0.0, -1.0],
            }
        ],
        "boundary_conditions": [
            {
                "id": "bc_001",
                "target_feature": "hole",
                "target_pointers": ["@face:face_003"],
                "type": "fixed",
            }
        ],
    }
    mapping = {
        "schema_version": "0.1",
        "topology_hash": "abc123",
        "stale": False,
        "mappings": [
            {
                "cae_entity": "BC1",
                "maps_to": {
                    "feature_id": "hole",
                    "role": "fixed_support",
                    "target_pointers": ["@face:face_003"],
                },
                "face_ids": ["face_003"],
            }
        ],
    }
    topology = {
        "format_version": "0.1.0",
        "entities": [
            {"id": "face_001", "type": "face", "surface_type": "plane", "bounding_box": [0, 0, 0, 10, 10, 0]},
            {"id": "face_002", "type": "face", "surface_type": "plane", "bounding_box": [0, 0, 0, 10, 0, 10]},
            {"id": "face_003", "type": "face", "surface_type": "cylinder", "bounding_box": [2, 2, 0, 4, 4, 10]},
        ],
    }
    if stale_face:
        setup["loads"][0]["target_face_ids"] = ["face_missing"]

    with zipfile.ZipFile(pkg_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps({"model_id": "test", "resources": {}}))
        if not missing_setup:
            zf.writestr("simulation/setup.yaml", yaml.safe_dump(setup, sort_keys=False))
            zf.writestr("simulation/cae_mapping.json", json.dumps(mapping))
        zf.writestr("geometry/topology_map.json", json.dumps(topology))


class TestCaeSetupOverlayEndpoint:
    def test_no_package_returns_available_false(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        client = TestClient(create_app(settings))
        project = save_project(settings, default_project("no-pkg"))

        resp = client.get(f"/api/projects/{project['id']}/cae-setup-overlay")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["reason"] == "no_package"
        assert body["loads"] == []
        assert body["constraints"] == []

    def test_no_setup_returns_available_false(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        client = TestClient(create_app(settings))
        project = save_project(settings, default_project("no-setup"))
        project_id = project["id"]
        pkg_path = project_dir(settings, project_id) / "test.aieng"
        _make_cae_package(pkg_path, missing_setup=True)
        project["aieng_file"] = "test.aieng"
        save_project(settings, project)

        resp = client.get(f"/api/projects/{project_id}/cae-setup-overlay")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["reason"] == "no_setup"

    def test_resolves_loads_and_constraints(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        client = TestClient(create_app(settings))
        project = save_project(settings, default_project("with-setup"))
        project_id = project["id"]
        pkg_path = project_dir(settings, project_id) / "test.aieng"
        _make_cae_package(pkg_path)
        project["aieng_file"] = "test.aieng"
        save_project(settings, project)

        resp = client.get(f"/api/projects/{project_id}/cae-setup-overlay")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["analysis_type"] == "static_structural"
        assert body["material_name"] == "Al6061-T6"
        assert body["mesh_target_size_mm"] == 2.5
        assert len(body["loads"]) == 1
        assert body["loads"][0]["magnitude_n"] == 500.0
        assert body["loads"][0]["direction"] == [0.0, 0.0, -1.0]
        assert body["loads"][0]["face_ids"] == ["face_002"]
        assert len(body["constraints"]) == 1
        assert body["constraints"][0]["face_ids"] == ["face_003"]
        assert body["warnings"] == []

    def test_flags_stale_face_references(self, tmp_path: Path) -> None:
        settings = _make_settings(tmp_path)
        client = TestClient(create_app(settings))
        project = save_project(settings, default_project("stale-setup"))
        project_id = project["id"]
        pkg_path = project_dir(settings, project_id) / "test.aieng"
        _make_cae_package(pkg_path, stale_face=True)
        project["aieng_file"] = "test.aieng"
        save_project(settings, project)

        resp = client.get(f"/api/projects/{project_id}/cae-setup-overlay")
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert len(body["warnings"]) == 1
        assert "face_missing" in body["warnings"][0]
