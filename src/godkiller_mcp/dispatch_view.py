"""View-mode tool handlers (extracted from dispatch monolith)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.types import TextContent

from godkiller_mcp.schema import EvidenceType


async def handle(name: str, arguments: Dict[str, Any]) -> Optional[List[TextContent]]:
    from godkiller_mcp.dispatch import _json, store

    if name == "view_start":
        from godkiller_mcp import view_engine as ve

        out = ve.start_view(
            arguments.get("goal") or arguments.get("target") or "",
            gravity=arguments.get("gravity") or "G2",
            task_id=arguments.get("task_id") or "",
        )
        task_id = arguments.get("task_id")
        if task_id:
            store.update_metadata(task_id, {"view_campaign": out["view"], "mode": "view"})
            out["task_id"] = task_id
        return _json(out)

    if name == "view_record_search":
        from godkiller_mcp import view_engine as ve

        task_id = arguments["task_id"]
        state = store.get(task_id)
        view = ve.get_view(state.handle.metadata)
        out = ve.record_search(
            view,
            query=arguments.get("query") or "",
            url=arguments.get("url") or "",
            backend=arguments.get("backend") or "host_web_search",
            note=arguments.get("note") or "",
        )
        store.update_metadata(task_id, {"view_campaign": out["view"]})
        return _json(out)

    if name == "view_record_attack":
        from godkiller_mcp import view_engine as ve

        task_id = arguments["task_id"]
        state = store.get(task_id)
        view = ve.get_view(state.handle.metadata)
        attack = arguments.get("attack")
        if not isinstance(attack, dict):
            attack = {
                "text": arguments.get("text") or arguments.get("weakness"),
                "quote": arguments.get("quote"),
                "doi_or_url": arguments.get("doi_or_url") or arguments.get("url"),
                "locator": arguments.get("locator"),
                "stance": arguments.get("stance"),
                "taxonomy": arguments.get("taxonomy") or arguments.get("kind"),
                "severity": arguments.get("severity"),
                "outcompete": arguments.get("outcompete"),
                "page_excerpt": arguments.get("page_excerpt") or arguments.get("excerpt"),
            }
        else:
            attack = dict(attack)
            if not attack.get("page_excerpt"):
                attack["page_excerpt"] = arguments.get("page_excerpt") or arguments.get("excerpt")
        out = ve.record_attack(view, attack)
        store.update_metadata(task_id, {"view_campaign": out["view"]})
        return _json(out)

    if name == "view_draft_plan":
        from godkiller_mcp import view_engine as ve

        task_id = arguments["task_id"]
        state = store.get(task_id)
        view = ve.get_view(state.handle.metadata)
        steps = arguments.get("steps") or arguments.get("plan") or {}
        out = ve.draft_plan(view, steps)
        store.update_metadata(task_id, {"view_campaign": out["view"]})
        if out.get("ok"):
            store.update_metadata(
                task_id,
                {"plan_dict": {"goal": view.get("goal"), "steps": out["view"]["plan_steps"]}},
            )
        return _json(out)

    if name == "view_refute_plan":
        from godkiller_mcp import view_engine as ve

        task_id = arguments["task_id"]
        state = store.get(task_id)
        view = ve.get_view(state.handle.metadata)
        out = ve.refute_plan(
            view,
            findings=arguments.get("findings") or [],
            decision=arguments.get("decision") or "HOLD",
        )
        store.update_metadata(task_id, {"view_campaign": out["view"]})
        return _json(out)

    if name == "view_finalize":
        from godkiller_mcp import view_engine as ve

        task_id = arguments["task_id"]
        state = store.get(task_id)
        view = ve.get_view(state.handle.metadata)
        out = ve.finalize(view, arguments.get("report") or arguments.get("content") or "")
        store.update_metadata(task_id, {"view_campaign": out["view"]})
        if out.get("ok"):
            store.submit_evidence(
                task_id,
                EvidenceType.LOG,
                "view_finalize sealed",
                {**out, "source": "view_finalize", "server_authored": True},
                server_authored=True,
            )
        return _json(out)

    return None
