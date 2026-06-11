"""Resolved optimization-variable document builder (#102)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

DESIGN_STUDY_PROBLEM_PATH = "analysis/design_study_problem.json"

_SHAPE_BEARING_TOKENS = frozenset({
    "fillet", "chamfer", "hole", "slot", "rib", "gusset",
    "taper", "draft", "position", "diameter", "radius",
})
_STOPTOKENS = frozenset({"mm", "cm", "m", "deg", "value", "param", "parameters"})
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: Any) -> set[str]:
    return {t for t in _TOKEN_RE.findall(str(text or "").lower()) if t not in _STOPTOKENS}


def is_shape_bearing_variable(variable: dict[str, Any]) -> bool:
    """Return True when a variable matches the Phase-3 shape-bearing catalog."""
    if not isinstance(variable, dict):
        return False
    sources = [
        variable.get("semantic_role"),
        variable.get("cad_parameter_name"),
        variable.get("parameterName"),
        variable.get("featureId"),
        variable.get("feature_name"),
    ]
    tokens: set[str] = set()
    for source in sources:
        tokens |= _tokens(source)
    if "radius" in tokens:
        if tokens & {"fillet", "chamfer", "hole", "slot", "corner"}:
            return True
        tokens.discard("radius")
    return bool(tokens & _SHAPE_BEARING_TOKENS)


def _coerce_variable(source: dict[str, Any], *, index_entry: dict[str, Any] | None) -> dict[str, Any]:
    vtype = source.get("type", "continuous")
    if index_entry:
        feature_id = index_entry.get("feature_id")
        parameter_name = index_entry.get("parameter_name")
        cad_parameter_name = index_entry.get("cad_parameter_name")
        binding_status = "bound"
    else:
        feature_id = source.get("featureId")
        parameter_name = source.get("parameterName")
        cad_parameter_name = source.get("cad_parameter_name")
        binding_status = "unverified"
    resolved: dict[str, Any] = {
        "id": source["id"],
        "path": source.get("path", ""),
        "type": vtype,
        "featureId": feature_id,
        "parameterName": parameter_name,
        "cad_parameter_name": cad_parameter_name,
        "binding_status": binding_status,
        "current_value": source.get("current_value"),
        "min_value": source.get("min_value"),
        "max_value": source.get("max_value"),
        "allowed_values": source.get("allowed_values"),
        "unit": source.get("unit"),
        "scope": source.get("scope", "unscoped"),
        "safe_to_modify": bool(source.get("safe_to_modify")),
        "semantic_role": source.get("semantic_role"),
        "candidate_ids": list(source.get("candidate_ids") or []),
    }
    resolved["shape_bearing"] = is_shape_bearing_variable({
        **resolved,
        "feature_name": index_entry.get("feature_name") if index_entry else None,
    })
    return resolved


def resolve_optimization_variables(
    design_study_problem: dict[str, Any],
    *,
    study_id: str,
    parameter_index: list[dict[str, Any]] | None = None,
    created_by: str = "aieng.converters.optimization_variables",
) -> dict[str, Any]:
    """Resolve design-study variables into an optimization_variables document."""
    problem = design_study_problem if isinstance(design_study_problem, dict) else {}
    problem_id = problem.get("id")
    index_by_cad_name: dict[str, dict[str, Any]] = {}
    if isinstance(parameter_index, list):
        for entry in parameter_index:
            if isinstance(entry, dict) and entry.get("cad_parameter_name"):
                index_by_cad_name[str(entry["cad_parameter_name"])] = entry
    variables: list[dict[str, Any]] = []
    for src in problem.get("variables") or []:
        if not isinstance(src, dict) or not src.get("id"):
            continue
        cad_name = src.get("cad_parameter_name")
        entry = index_by_cad_name.get(str(cad_name)) if cad_name else None
        variables.append(_coerce_variable(src, index_entry=entry))
    return {
        "format": "aieng.optimization_variables",
        "schema_version": "0.2",
        "study_id": study_id,
        "design_study_problem_ref": DESIGN_STUDY_PROBLEM_PATH,
        "design_study_problem_id": problem_id,
        "variables": variables,
        "candidate_ids": [],
        "provenance": {
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "created_by": created_by,
            "claim_advancement": "none",
        },
        "claim_policy": {
            "advisory_only": True,
            "baseline_unchanged": True,
            "human_approval_required_for_acceptance": True,
            "claim_advancement": "none",
        },
    }
