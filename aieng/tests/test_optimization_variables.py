"""Tests for optimization variable resolution + shape-bearing tagging (#102)."""
from __future__ import annotations

import pytest

from aieng.converters.optimization_variables import (
    is_shape_bearing_variable,
    resolve_optimization_variables,
)
from aieng.optimization_artifacts import validate_optimization_artifact_set


def _problem(variables):
    return {
        "format": "aieng.design_study_problem",
        "schema_version": "0.1",
        "id": "study_001",
        "variables": variables,
        "objective": {"sense": "minimize", "metric": "mass"},
        "constraints": [],
    }


# ── shape-bearing recognition ────────────────────────────────────────────────


@pytest.mark.parametrize("name", [
    "FILLET_RADIUS",
    "fillet_radius",
    "CORNER_FILLET",
    "hole_diameter",
    "HOLE_DIA",
    "slot_position",
    "SLOT_DIA",
    "rib_thickness",
    "gusset_width",
    "chamfer_size",
    "wall_taper",
    "draft_angle",
])
def test_shape_bearing_true_for_catalog_params(name):
    assert is_shape_bearing_variable({"cad_parameter_name": name}) is True


@pytest.mark.parametrize("name", [
    "WALL_THICKNESS",
    "bracket_width",
    "flange_height",
    "mounting_distance",
    "part_length",
])
def test_shape_bearing_false_for_sizing_params(name):
    assert is_shape_bearing_variable({"cad_parameter_name": name}) is False


def test_radius_requires_shape_context():
    # Corner radius is shape-bearing via context.
    assert is_shape_bearing_variable({"cad_parameter_name": "CORNER_RADIUS"}) is True
    # Generic part radius without feature word → false.
    assert is_shape_bearing_variable({"cad_parameter_name": "PART_RADIUS"}) is False


def test_semantic_role_triggers_shape_bearing():
    assert is_shape_bearing_variable({"semantic_role": "fillet"}) is True
    assert is_shape_bearing_variable({"semantic_role": "wall_thickness"}) is False


# ── full resolution ──────────────────────────────────────────────────────────


def test_resolve_optimization_variables_tags_shape_bearing():
    problem = _problem([
        {"id": "wall_t", "path": "p/WALL_THICKNESS", "type": "continuous",
         "current_value": 3.0, "min_value": 2.0, "max_value": 8.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "WALL_THICKNESS"},
        {"id": "fillet_r", "path": "p/FILLET_RADIUS", "type": "continuous",
         "current_value": 2.0, "min_value": 0.5, "max_value": 5.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "FILLET_RADIUS"},
        {"id": "hole_d", "path": "p/HOLE_DIA", "type": "continuous",
         "current_value": 10.0, "min_value": 5.0, "max_value": 20.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "HOLE_DIA"},
    ])
    doc = resolve_optimization_variables(problem, study_id="opt_001")
    by_id = {v["id"]: v for v in doc["variables"]}
    assert by_id["wall_t"]["shape_bearing"] is False
    assert by_id["fillet_r"]["shape_bearing"] is True
    assert by_id["hole_d"]["shape_bearing"] is True


def test_resolve_uses_parameter_index_for_binding():
    problem = _problem([
        {"id": "wall_t", "path": "p/WALL_THICKNESS", "type": "continuous",
         "current_value": 3.0, "min_value": 2.0, "max_value": 8.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "WALL_THICKNESS"},
    ])
    index = [{
        "feature_id": "feat_wall",
        "feature_name": "Wall",
        "feature_type": "named_part",
        "scope": "local",
        "parameter_name": "thickness",
        "cad_parameter_name": "WALL_THICKNESS",
        "current_value": 3.0,
        "min_value": 2.0,
        "max_value": 8.0,
        "search_tokens": ["wall", "thickness"],
    }]
    doc = resolve_optimization_variables(problem, study_id="opt_001", parameter_index=index)
    var = doc["variables"][0]
    assert var["binding_status"] == "bound"
    assert var["featureId"] == "feat_wall"
    assert var["parameterName"] == "thickness"


def test_resolved_document_validates_against_schema():
    problem = _problem([
        {"id": "wall_t", "path": "p/WALL_THICKNESS", "type": "continuous",
         "current_value": 3.0, "min_value": 2.0, "max_value": 8.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "WALL_THICKNESS"},
        {"id": "fillet_r", "path": "p/FILLET_RADIUS", "type": "continuous",
         "current_value": 2.0, "min_value": 0.5, "max_value": 5.0,
         "unit": "mm", "safe_to_modify": True, "cad_parameter_name": "FILLET_RADIUS"},
    ])
    doc = resolve_optimization_variables(problem, study_id="opt_001")
    issues = validate_optimization_artifact_set(
        {"variables": doc},
        design_study_problem=problem,
    )
    assert issues == []


def test_resolved_document_has_v02_schema():
    problem = _problem([
        {"id": "wall_t", "path": "p/WALL_THICKNESS", "type": "continuous",
         "current_value": 3.0, "min_value": 2.0, "max_value": 8.0,
         "unit": "mm", "safe_to_modify": True},
    ])
    doc = resolve_optimization_variables(problem, study_id="opt_001")
    assert doc["schema_version"] == "0.2"
    assert doc["format"] == "aieng.optimization_variables"
