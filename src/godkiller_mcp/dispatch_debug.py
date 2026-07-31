"""Debug Self-CTF tool handlers (extracted from dispatch monolith)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from godkiller_mcp.schema import EvidenceType


async def handle(name: str, arguments: Dict[str, Any]) -> Optional[List[TextContent]]:
    from godkiller_mcp.dispatch import _json, store

    if name == "debug_self_ctf_start":
        from godkiller_mcp import debug_engine as de

        task_id = arguments.get("task_id") or ""
        out = de.start(
            workspace=arguments.get("workspace") or ".",
            goal=arguments.get("goal") or "",
            max_rounds=int(arguments.get("max_rounds") or 8),
            task_id=task_id,
        )
        if task_id and out.get("ok"):
            store.update_metadata(
                task_id,
                {"debug_self_ctf": out["ctf"], "require_self_ctf": True, "mode": "debug"},
            )
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary="debug_self_ctf_start armed (workspace only)",
                payload={**out, "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    if name == "debug_self_ctf_tick":
        from godkiller_mcp import debug_engine as de

        task_id = arguments["task_id"]
        state = store.get(task_id)
        ctf = de.get_ctf(state.handle.metadata)
        if not ctf:
            return _json({"ok": False, "reason": "call debug_self_ctf_start first"})
        out = de.tick(ctf)
        store.update_metadata(task_id, {"debug_self_ctf": out.get("ctf") or ctf})
        if arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=(
                    f"debug_self_ctf_tick r={(out.get('ctf') or {}).get('round')} "
                    f"status={(out.get('ctf') or {}).get('status')} added={out.get('added')}"
                ),
                payload={**out, "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    if name == "debug_self_ctf_run_until":
        from godkiller_mcp import debug_engine as de

        task_id = arguments["task_id"]
        state = store.get(task_id)
        ctf = de.get_ctf(state.handle.metadata)
        if not ctf:
            # auto-start
            started = de.start(
                workspace=arguments.get("workspace") or ".",
                goal=arguments.get("goal")
                or (getattr(state.handle, "goal", None) or ""),
                max_rounds=int(arguments.get("max_rounds") or 8),
                task_id=task_id,
            )
            ctf = started["ctf"]
            store.update_metadata(
                task_id,
                {"debug_self_ctf": ctf, "require_self_ctf": True, "mode": "debug"},
            )
        out = de.run_until(ctf, link_fault_probe=bool(arguments.get("fault_probe", True)))
        store.update_metadata(task_id, {"debug_self_ctf": out.get("ctf") or ctf})
        if arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=(
                    f"debug_self_ctf_run_until status={(out.get('ctf') or {}).get('status')} "
                    f"findings={len((out.get('ctf') or {}).get('findings') or [])}"
                ),
                payload={**out, "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    return None
