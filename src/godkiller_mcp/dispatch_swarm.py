"""Swarm + write_guard tool handlers (extracted from dispatch monolith)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from godkiller_mcp.schema import EvidenceType


async def handle(name: str, arguments: Dict[str, Any]) -> Optional[List[TextContent]]:
    from godkiller_mcp.dispatch import _json, store

    if name == "write_guard":
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
        decision = decide_write(
            path=arguments["path"],
            workspace=arguments.get("workspace") or ".",
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
        from godkiller_mcp.write_guard import persist_allow_paths

        paths = arguments.get("paths") or []
        task_id = arguments.get("task_id") or ""
        workspace = arguments.get("workspace") or "."
        if task_id:
            store.update_metadata(task_id, {"write_allow_paths": list(paths)})
            if arguments.get("require_swarm"):
                store.update_metadata(task_id, {"require_swarm": True})
        path = persist_allow_paths(workspace, paths, task_id=task_id)
        return _json(
            {
                "ok": True,
                "path": str(path),
                "paths": list(paths),
                "hint": "Point host PreToolUse hook at: python -m godkiller_mcp.write_guard --stdin",
            }
        )

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
