"""tool_propose / approve / reject / used handlers (additive capability gate)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from godkiller_mcp.schema import EvidenceType


async def handle(name: str, arguments: Dict[str, Any]) -> Optional[List[TextContent]]:
    from godkiller_mcp.dispatch import _json, store
    from godkiller_mcp import tool_propose as tp

    if name == "tool_propose":
        task_id = arguments.get("task_id") or ""
        out = tp.propose(
            arguments.get("need") or arguments.get("goal") or "",
            arguments.get("candidates") or [],
            min_n=int(arguments.get("min_n") or 5),
            max_n=int(arguments.get("max_n") or 10),
            workspace=arguments.get("workspace") or ".",
            task_id=task_id,
        )
        if out.get("ok") and arguments.get("enrich"):
            enriched = tp.enrich_scrape(out["tool_propose"], arguments.get("enrich_ids"))
            if enriched.get("ok"):
                out = {**out, **enriched, "ok": True}
                out["tool_propose"] = enriched["tool_propose"]
        if task_id and out.get("ok"):
            store.update_metadata(task_id, {"tool_propose": out["tool_propose"]})
            if arguments.get("attach", True):
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.LOG,
                    summary=f"tool_propose n={out.get('count')}",
                    payload={**out, "server_authored": True},
                    server_authored=True,
                )
        return _json(out)

    if name == "tool_approve":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        cur = tp.get_state(state.handle.metadata)
        out = tp.approve(
            cur,
            arguments.get("ids") or arguments.get("proposal_ids") or [],
            workspace=arguments.get("workspace") or cur.get("workspace") or ".",
        )
        if out.get("ok"):
            store.update_metadata(task_id, {"tool_propose": out["tool_propose"]})
            if arguments.get("attach", True):
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.LOG,
                    summary=f"tool_approve {out['tool_propose'].get('approved_ids')}",
                    payload={**out, "server_authored": True},
                    server_authored=True,
                )
        return _json(out)

    if name == "tool_reject_all":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        cur = tp.get_state(state.handle.metadata)
        out = tp.reject_all(cur, arguments.get("reason") or "")
        if out.get("ok"):
            store.update_metadata(task_id, {"tool_propose": out["tool_propose"]})
            if arguments.get("attach", True):
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.LOG,
                    summary="tool_reject_all",
                    payload={**out, "server_authored": True},
                    server_authored=True,
                )
        return _json(out)

    if name == "tool_used":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        cur = tp.get_state(state.handle.metadata)
        out = tp.record_used(
            cur,
            arguments.get("proposal_id") or arguments.get("id") or "",
            arguments.get("how") or "",
        )
        if out.get("ok"):
            store.update_metadata(task_id, {"tool_propose": out["tool_propose"]})
            if arguments.get("attach", True):
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.LOG,
                    summary=f"tool_used {out.get('entry', {}).get('id')}",
                    payload={**out, "server_authored": True},
                    server_authored=True,
                )
        return _json(out)

    if name == "tool_propose_status":
        task_id = arguments.get("task_id") or ""
        if task_id:
            state = store.get(task_id)
            cur = tp.get_state(state.handle.metadata)
        else:
            cur = {}
        return _json(tp.status_payload(cur))

    return None
