"""Swarm + write_guard tool handlers (extracted from dispatch monolith)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from godkiller_mcp.schema import EvidenceType


async def handle(name: str, arguments: Dict[str, Any]) -> Optional[List[TextContent]]:
    from godkiller_mcp.dispatch import _json, store

    if name == "write_guard":
        from pathlib import Path

        from godkiller_mcp.path_sandbox import WorkspaceRootError, workspace_root
        from godkiller_mcp.ship_mode import relax_enabled
        from godkiller_mcp.write_guard import collect_allow_paths, decide_write

        task_id = arguments.get("task_id")
        allow = list(arguments.get("allow_paths") or [])
        if task_id:
            try:
                allow = collect_allow_paths(store.get(task_id), explicit=allow)
            except Exception:
                pass
        require_al = bool(arguments.get("require_allowlist", True))
        if not relax_enabled():
            require_al = True
        try:
            auth = workspace_root()
        except WorkspaceRootError as exc:
            return _json(
                {
                    "allowed": False,
                    "permissionDecision": "deny",
                    "reason": str(exc),
                    "error": "workspace_root_unpinned",
                }
            )
        raw_ws = arguments.get("workspace")
        if raw_ws and Path(str(raw_ws)).expanduser().resolve() != auth.resolve():
            return _json(
                {
                    "allowed": False,
                    "permissionDecision": "deny",
                    "reason": "workspace_root_rebinding_refused for write_guard",
                    "error": "workspace_root_rebinding_refused",
                    "workspace": str(auth),
                }
            )
        decision = decide_write(
            path=arguments["path"],
            workspace=auth,
            allow_paths=allow,
            require_allowlist=require_al,
            tool_name=arguments.get("tool_name") or "Write",
        )
        if task_id and arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=decision["reason"],
                payload={**decision, "source": "write_guard", "server_authored": True},
                server_authored=True,
            )
        return _json(decision)

    if name == "write_guard_set_paths":
        from pathlib import Path

        from godkiller_mcp.path_sandbox import (
            WorkspaceRootError,
            ensure_under_root,
            path_gate_error,
            workspace_root,
        )
        from godkiller_mcp.write_guard import persist_allow_paths

        paths = arguments.get("paths") or []
        task_id = arguments.get("task_id") or ""
        phase = str(arguments.get("phase") or arguments.get("phase_id") or "").strip()
        try:
            auth = workspace_root()
        except WorkspaceRootError as exc:
            return _json({"ok": False, "error": "workspace_root_unpinned", "detail": str(exc)})
        raw_ws = arguments.get("workspace")
        if raw_ws and Path(str(raw_ws)).expanduser().resolve() != auth.resolve():
            return _json(
                {
                    "ok": False,
                    "error": "workspace_root_rebinding_refused",
                    "detail": "write_guard_set_paths workspace must match GODKILLER_WORKSPACE/cwd pin",
                    "workspace": str(auth),
                }
            )
        clean_paths: list[str] = []
        for p in paths:
            bad = path_gate_error(p)
            if bad:
                return _json({**bad, "ok": False, "hint": "paths must stay under workspace pin"})
            try:
                rel = ensure_under_root(p).relative_to(auth)
                clean_paths.append(str(rel).replace("\\", "/"))
            except Exception:
                clean_paths.append(str(p).replace("\\", "/").lstrip("./"))
        try:
            path = persist_allow_paths(
                auth,
                clean_paths,
                task_id=task_id,
                phase=phase or "turn",
                force=bool(arguments.get("force", False)),
                source="set_paths",
            )
        except ValueError as exc:
            return _json(
                {
                    "ok": False,
                    "error": "write_turn_locked",
                    "detail": str(exc),
                    "hint": "Call gk_guard.end_turn after this Phase, then set_paths for the next Phase only.",
                }
            )
        if task_id:
            store.update_metadata(
                task_id,
                {"write_allow_paths": list(clean_paths), "write_phase": phase or "turn"},
            )
            if arguments.get("require_swarm"):
                store.update_metadata(task_id, {"require_swarm": True})
        return _json(
            {
                "ok": True,
                "path": str(path),
                "paths": list(clean_paths),
                "phase": phase or "turn",
                "workspace": str(auth),
                "hint": (
                    "Host PreToolUse → godkiller-write-guard. "
                    "One path set per turn (ship default max 1). "
                    "After this Phase: gk_guard.end_turn then stop the host turn."
                ),
            }
        )

    if name == "write_guard_end_turn":
        from pathlib import Path

        from godkiller_mcp.path_sandbox import WorkspaceRootError, workspace_root
        from godkiller_mcp.write_guard import end_write_turn

        task_id = arguments.get("task_id") or ""
        try:
            auth = workspace_root()
        except WorkspaceRootError as exc:
            return _json({"ok": False, "error": "workspace_root_unpinned", "detail": str(exc)})
        raw_ws = arguments.get("workspace")
        if raw_ws and Path(str(raw_ws)).expanduser().resolve() != auth.resolve():
            return _json(
                {
                    "ok": False,
                    "error": "workspace_root_rebinding_refused",
                    "detail": "write_guard_end_turn workspace must match pin",
                    "workspace": str(auth),
                }
            )
        out = end_write_turn(auth, task_id=task_id)
        if task_id:
            store.update_metadata(task_id, {"write_allow_paths": [], "write_turn_open": False})
        return _json(out)

    if name == "swarm_spawn":
        from godkiller_mcp.swarm import spawn_swarm
        from godkiller_mcp.write_guard import persist_allow_paths

        out = spawn_swarm(
            arguments["goal"],
            workspace=arguments.get("workspace") or ".",
            mode=arguments.get("mode") or "host",
            task_id=arguments.get("task_id") or "",
            context=arguments.get("context") or {},
        )
        task_id = arguments.get("task_id")
        if task_id:
            store.update_metadata(
                task_id,
                {
                    "swarm_session_id": out.get("session_id"),
                    "require_swarm": bool(arguments.get("require_swarm", True)),
                },
            )
        if out.get("write_allow_paths"):
            persist_allow_paths(
                arguments.get("workspace") or ".",
                out["write_allow_paths"],
                task_id=task_id or "",
                force=True,
                source="swarm",
            )
            if task_id:
                store.update_metadata(task_id, {"write_allow_paths": out["write_allow_paths"]})
        if task_id and arguments.get("attach", True) and out.get("api_ran"):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=f"swarm_spawn {out.get('session_id')}",
                payload={**out, "source": "swarm_spawn", "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    if name == "swarm_submit":
        from godkiller_mcp.swarm import submit_role

        payload = arguments.get("payload") or {
            "findings": arguments.get("findings"),
            "must_fix": arguments.get("must_fix"),
            "paths": arguments.get("paths"),
            "vote": arguments.get("vote"),
            "severity": arguments.get("severity"),
            "commands": arguments.get("commands"),
            "checks": arguments.get("checks"),
            "steps": arguments.get("steps"),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        return _json(
            submit_role(
                arguments["session_id"],
                arguments["role"],
                payload,
            )
        )

    if name == "swarm_collect":
        from godkiller_mcp.swarm import collect_swarm
        from godkiller_mcp.write_guard import persist_allow_paths

        out = collect_swarm(arguments["session_id"])
        task_id = arguments.get("task_id")
        if out.get("write_allow_paths") and arguments.get("workspace"):
            persist_allow_paths(
                arguments["workspace"],
                out["write_allow_paths"],
                task_id=task_id or "",
                force=True,
                source="swarm",
            )
        if task_id and out.get("write_allow_paths"):
            store.update_metadata(task_id, {"write_allow_paths": out["write_allow_paths"]})
        if task_id and arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=f"swarm_collect {'PASS' if out.get('passed') else 'FAIL'}",
                payload={**out, "source": "swarm_collect", "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    return None
