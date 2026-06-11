"""Agent/onboarding runtime tool registrations.

Extracted from ``runtime_tool_registry.py`` as the first domain in the
runtime-registry split proof-of-concept.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..legacy_app_symbols import sync_main_symbols


def register_agent_tools(rt: Any, active_settings: Any, app_context: Any, _schema: Any) -> None:
    """Register agent/onboarding runtime tools."""
    sync_main_symbols(globals())

    _delete_project_everywhere = app_context.delete_project_everywhere

    # ── agent onboarding tools ────────────────────────────────────────────────

    def _tool_aieng_list_projects(_inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """List all .aieng projects the workbench knows about.

        Broken projects (missing or unreadable metadata) are filtered out so the
        agent never receives a project_id that would later return 404.
        """
        projects: list[dict[str, Any]] = []
        for path in active_settings.projects_root.glob("*/metadata.json"):
            metadata = read_json(path, None)  # noqa: F821
            if metadata is None:
                continue  # unreadable / broken metadata
            if not isinstance(metadata, dict):
                continue
            if not metadata.get("id"):
                continue  # missing project_id — would cause 404 downstream
            projects.append(normalize_project(metadata))  # noqa: F821
        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return {"projects": projects, "count": len(projects)}

    rt.register_tool(
        "aieng.list_projects",
        _tool_aieng_list_projects,
        description=(
            "List all projects available in this workbench instance. Returns id, "
            "name, status, last-modified, and (for agent-built geometry) named_parts "
            "+ part_count for each project. Call this first if you don't know which "
            "project_id to use; use aieng.find_projects_by_part to locate a project "
            "by a part label."
        ),
        input_schema=_schema("aieng.list_projects"),
    )

    def _tool_aieng_create_project(_inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """Create a new empty project."""
        from ..project_io import default_project, save_project

        name = str(_inp.get("name") or "").strip() or "Untitled project"
        project = save_project(active_settings, default_project(name))
        return {
            "id": project["id"],
            "name": project["name"],
            "status": project.get("status", "empty"),
            "created_at": project.get("created_at"),
            "message": f"Project '{project['name']}' created successfully.",
        }

    rt.register_tool(
        "aieng.create_project",
        _tool_aieng_create_project,
        description=(
            "Create a new empty workbench project. Returns the project's id, name, "
            "and status. Use this when the user wants to start CAD modeling from "
            "scratch and no suitable existing project is available. The returned "
            "id can be passed directly to geometry-mutation tools such as "
            "cad.execute_build123d."
        ),
        input_schema=_schema("aieng.create_project"),
    )

    def _tool_aieng_find_projects_by_part(_inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """Find projects whose geometry contains a named part matching the query.

        Scans each project's metadata ``named_parts`` (cheap; populated on every
        agent build); for older projects without that field it falls back to
        reading the package's feature graph. Substring, case-insensitive.
        """
        from ..cad_generation import _named_parts_from_package
        from ..project_io import resolve_project_path

        query = str(_inp.get("query") or "").strip().lower()
        if not query:
            return {"query": "", "matches": [], "count": 0}
        matches: list[dict[str, Any]] = []
        for path in active_settings.projects_root.glob("*/metadata.json"):
            proj = normalize_project(read_json(path, {}))  # noqa: F821
            parts = proj.get("named_parts")
            if not isinstance(parts, list):
                parts = []
                pkg_path = resolve_project_path(active_settings, proj["id"], proj.get("aieng_file"))
                if pkg_path and pkg_path.exists():
                    parts = _named_parts_from_package(pkg_path)
            hits = [str(p) for p in parts if query in str(p).lower()]
            if hits:
                matches.append({
                    "id": proj["id"],
                    "name": proj["name"],
                    "status": proj.get("status"),
                    "matched_parts": hits,
                    "part_count": len(parts),
                })
        matches.sort(key=lambda m: (-len(m["matched_parts"]), m["name"]))
        return {"query": query, "matches": matches, "count": len(matches)}

    rt.register_tool(
        "aieng.find_projects_by_part",
        _tool_aieng_find_projects_by_part,
        description=(
            "Find projects whose geometry contains a named part matching the query "
            "(case-insensitive substring on part labels). Use this to locate a model "
            "by content, e.g. find which project holds the 'optimus' parts."
        ),
        input_schema=_schema("aieng.find_projects_by_part"),
    )

    def _tool_aieng_delete_project(_inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """Permanently delete a project: its directory + chat sessions/messages."""
        pid = str(_inp.get("project_id") or "").strip()
        if not pid:
            return {"status": "error", "message": "project_id is required"}
        try:
            result = _delete_project_everywhere(pid)
        except HTTPException:
            return {"status": "error", "code": "not_found", "message": f"project not found: {pid}"}
        return {"status": "ok", **result}

    rt.register_tool(
        "aieng.delete_project",
        _tool_aieng_delete_project,
        description=(
            "[APPROVAL REQUIRED] Permanently delete a project — its .aieng package, "
            "metadata, viewer assets, and all chat sessions/messages. Irreversible. "
            "Confirm with the user before calling."
        ),
        input_schema=_schema("aieng.delete_project"),
        requires_approval=True,
    )

    def _tool_inspect_package(inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        pid = inp.get("project_id")
        if not pid:
            raise ValueError("project_id is required for aieng.inspect_package")
        return package_summary(active_settings, pid)  # noqa: F821

    def _tool_agent_context(inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        from .. import agent_context

        pid = inp.get("project_id")
        if not pid:
            raise ValueError("project_id is required for aieng.agent_context")
        return agent_context.build_agent_context(active_settings, str(pid))

    def _tool_aieng_agent_readme(inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """Return compact onboarding by default, with a full-guide compatibility mode."""
        from .. import agent_guides

        if str(inp.get("detail") or "quickstart").lower() == "full":
            result = agent_guides.full_result()
        else:
            result = agent_guides.quickstart_result()
        # Registry identity so an agent can tell if this long-lived MCP session
        # is serving a stale tool set (#29) — compare against GET /api/health.
        result["registry"] = rt.registry_identity()
        return result

    rt.register_tool(
        "aieng.agent_readme",
        _tool_aieng_agent_readme,
        description=(
            "Return compact operational onboarding. Read this once at the start of a session, "
            "then use aieng.guide only for task-specific detail. detail=full preserves access "
            "to the canonical complete AGENTS.md."
        ),
        input_schema=_schema("aieng.agent_readme"),
    )

    def _tool_aieng_guide(inp: dict[str, Any], _ctx: dict[str, Any]) -> dict[str, Any]:
        """Return one detailed guide topic extracted from canonical AGENTS.md."""
        from .. import agent_guides

        return agent_guides.guide_result(str(inp.get("topic") or ""))

    rt.register_tool(
        "aieng.guide",
        _tool_aieng_guide,
        description=(
            "Return task-specific detail extracted from the canonical AGENTS.md without "
            "loading the full guide. Topics include cad, cae, pointers, tools, workflows, "
            "package, fallback, frontend, approvals, operators, and full."
        ),
        input_schema=_schema("aieng.guide"),
    )

    rt.register_tool(
        "aieng.inspect_package",
        _tool_inspect_package,
        description=(
            "Inspect a .aieng package and return the full project semantic summary "
            "(geometry, CAE setup, results, verdict, design targets). "
            "Call this first when starting work on a project to understand its current state."
        ),
        input_schema=_schema("aieng.inspect_package"),
    )
    rt.register_tool(
        "aieng.agent_context",
        _tool_agent_context,
        description=(
            "Build compact agent-facing CAD/CAE context for a project. "
            "Includes package summary, recent audit log, validation status, "
            "and a short task checklist."
        ),
        input_schema=_schema("aieng.agent_context"),
    )
