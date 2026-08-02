"""Domain handlers peeled from dispatch (facade names unchanged)."""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.types import TextContent


async def handle(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    import json

    from godkiller_mcp.runtime_state import (
        AGENTS_ROOT,
        _json,
        marathon,
        modes,
        store,
    )
    from godkiller_mcp import ultradeep_engine as ude
    from godkiller_mcp.schema import EvidenceType, PolicyAction
    from godkiller_mcp.skill_catalog import (
        build_catalog,
        filter_catalog,
        suggest_from_catalog,
    )

    arguments = arguments or {}
    if name == "list_modes":
        return _json({"modes": modes.list_modes()})

    if name == "get_protocol":
        text = modes.get_protocol(arguments["mode"])
        return _json({"mode": arguments["mode"], "protocol_markdown": text})

    if name == "get_constitution":
        return _json({"constitution_markdown": modes.get_constitution()})

    if name == "skill_catalog":
        from godkiller_mcp.skill_catalog import resolve_skill_roots
        from godkiller_mcp.skill_gates import build_catalog_evidence_payload

        roots = resolve_skill_roots(AGENTS_ROOT)
        entries = build_catalog(roots)
        query = arguments.get("query") or arguments.get("goal") or ""
        limit = int(arguments.get("limit") or 20)
        hits = filter_catalog(entries, query, limit=limit)
        shortlist_paths: List[str] = []
        ops_n = sum(1 for e in entries if e.get("family") == "agent-ops")
        out: Dict[str, Any] = {
            "total_indexed": len(entries),
            "agent_ops_indexed": ops_n,
            "roots": [str(r) for r in roots],
            "returned": len(hits),
            "query": query,
            "skills": hits,
            "rule": (
                "Catalog merges project .agents/skills + agent-ops (bundled). "
                "Thin index only — view_file at most 2–4 SKILL.md paths you pick, "
                "then record_skills_loaded. FORBIDDEN: skip because you feel confident."
            ),
        }
        goal = arguments.get("goal") or query
        if goal:
            from godkiller_mcp.modes import suggest_skills_for_goal

            forced = suggest_skills_for_goal(goal).get("must_view_file") or []
            pack = suggest_from_catalog(entries, goal, limit=4, forced_paths=forced)
            out["shortlist"] = pack
            shortlist_paths = pack.get("shortlist_paths") or []
        task_id = arguments.get("task_id")
        if task_id:
            payload = build_catalog_evidence_payload(
                query or goal,
                shortlist_paths=shortlist_paths,
                returned=len(hits),
            )
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"skill_catalog query={query or goal!r} n={len(hits)}",
                payload=payload,
            )
            store.update_metadata(
                task_id,
                {
                    "skill_catalog_query": query or goal,
                    "skill_catalog_shortlist": shortlist_paths,
                    "skill_scan_at": payload.get("source"),
                },
            )
            out["evidence_id"] = ev.id
            out["recorded"] = True
        else:
            out["recorded"] = False
            out["warn"] = "Pass task_id=... or phase/claim gates will BLOCK (overconfidence waiver denied)."
        return _json(out)

    if name == "record_skills_loaded":
        from godkiller_mcp.skill_gates import build_loaded_payload, loaded_gate

        paths = arguments.get("paths") or []
        if len(paths) > 4:
            return _json(
                {
                    "allowed": False,
                    "reason": "Max 4 skills_loaded (brain bloat).",
                    "action": PolicyAction.BLOCK.value,
                }
            )
        if len(paths) < 1:
            return _json(
                {
                    "allowed": False,
                    "reason": "Need at least 1 path after view_file.",
                    "action": PolicyAction.BLOCK.value,
                }
            )
        payload = build_loaded_payload(paths)
        ev = store.submit_evidence(
            task_id=arguments["task_id"],
            evidence_type=EvidenceType.OTHER,
            summary=f"skills_loaded n={len(payload['paths'])}",
            payload=payload,
        )
        store.update_metadata(arguments["task_id"], {"skills_loaded": payload["paths"]})
        ok, reason = loaded_gate(store.get(arguments["task_id"]))
        return _json(
            {
                "allowed": ok,
                "reason": reason,
                "evidence_id": ev.id,
                "paths": payload["paths"],
            }
        )

    if name == "activate_mode":
        mode = arguments["mode"]
        goal = arguments.get("goal") or ""
        payload = modes.activate(
            mode,
            goal,
            kind=arguments.get("kind"),
            slug=arguments.get("slug"),
            plan_phase=int(arguments.get("plan_phase") or 1),
            include_protocol=bool(
                arguments.get("include_protocol")
                or arguments.get("full_protocol")
                or arguments.get("verbose")
            ),
            verbose=bool(arguments.get("verbose")),
        )
        opened = None
        marathon_state = None
        if arguments.get("open_kernel_task", True) and mode in ("ask", "plan", "debug", "ultradeep", "view"):
            kind = arguments.get("kind") or payload["kind_suggestion"]
            opened_state = store.open_task(
                kind=kind,
                goal=goal or f"{mode} session",
                project_id=arguments.get("project_id") or "default",
            )
            opened = {
                "task_id": opened_state.handle.task_id,
                "kind": opened_state.handle.kind.value,
                "phase": opened_state.handle.phase.value,
                "rubric_id": opened_state.handle.rubric_id,
            }
            payload["task_id"] = opened_state.handle.task_id
            if mode == "ultradeep":
                slug = arguments.get("slug") or f"m_{opened_state.handle.task_id[-8:]}"
                try:
                    mstate = marathon.load(slug)
                except FileNotFoundError:
                    mstate = marathon.init(
                        slug=slug,
                        goal=goal or opened_state.handle.goal,
                        kind=kind,
                        plan_path=arguments.get("plan_path"),
                        task_id=opened_state.handle.task_id,
                    )
                # Enable per-file think→plan→edit gate (additive; opt-out per_file_gate=false)
                enable_pf = arguments.get("per_file_gate", True)
                existing = (mstate.metadata or {}).get("ultradeep_file_gate")
                if isinstance(existing, dict) and existing.get("queue"):
                    gate = ude.get_gate({"ultradeep_file_gate": existing})
                    gate["enabled"] = bool(enable_pf)
                else:
                    gate = ude.empty_file_gate(enabled=bool(enable_pf))
                # Persist on task + marathon metadata
                store.update_metadata(
                    opened_state.handle.task_id,
                    {
                        "ultradeep_file_gate": gate,
                        "mode": "ultradeep",
                        "marathon_slug": slug,
                        "require_swarm": True,
                    },
                )
                mstate = marathon.save(
                    slug,
                    task_id=opened_state.handle.task_id,
                    metadata={"ultradeep_file_gate": gate},
                    last_handoff=(
                        mstate.last_handoff
                        or (
                            "ultradeep armed: ONE phase this turn + per-file think→plan→edit. "
                            "Next: ultradeep_queue_files then ultradeep_think_file."
                        )
                    ),
                    bump_session=False,
                )
                marathon_state = json.loads(mstate.model_dump_json())
                payload["slug"] = slug
                payload["next_wake"] = marathon.next_wake_prompt(slug)
                payload["per_file_gate"] = ude.status_payload(gate)
                payload["power_mode"] = (
                    "200% Cursor-agent tool swarm + legacy ultradeep crucible + marathon pacing"
                )
            if mode == "debug":
                store.update_metadata(
                    opened_state.handle.task_id,
                    {"mode": "debug", "require_self_ctf": True},
                )
                payload["power_mode"] = (
                    "Self-CTF: debug_self_ctf_start → tick (workspace only) until findings"
                )
        return _json(
            {
                **payload,
                "opened_task": opened,
                "marathon": marathon_state,
            }
        )

    if name == "ultradeep_queue_files":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled") and arguments.get("force_enable", True):
            gate["enabled"] = True
        gate = ude.queue_files(
            gate,
            arguments.get("paths") or [],
            replace=bool(arguments.get("replace", False)),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": gate})
        slug = arguments.get("slug") or (state.handle.metadata or {}).get("marathon_slug")
        if slug:
            try:
                marathon.save(
                    slug,
                    metadata={"ultradeep_file_gate": gate},
                    last_handoff=f"Queued {len(gate.get('queue') or [])} files; current={gate.get('current')}",
                    bump_session=False,
                )
            except FileNotFoundError:
                pass
        return _json({"ok": True, **ude.status_payload(gate)})

    if name == "ultradeep_think_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled"):
            gate["enabled"] = True
        result = ude.record_think(
            gate,
            arguments["path"],
            arguments.get("think") or "",
            hypotheses=arguments.get("hypotheses"),
            tools_used=arguments.get("tools_used"),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        if result["ok"]:
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"ultradeep_think:{arguments['path']}",
                payload={
                    "path": arguments["path"],
                    "hypotheses": arguments.get("hypotheses") or [],
                    "tools_used": arguments.get("tools_used") or [],
                    "think_len": len(arguments.get("think") or ""),
                },
            )
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_plan_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled"):
            gate["enabled"] = True
        result = ude.record_plan(
            gate,
            arguments["path"],
            arguments.get("plan") or "",
            tools_used=arguments.get("tools_used"),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        if result["ok"]:
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"ultradeep_plan:{arguments['path']}",
                payload={"path": arguments["path"], "plan_len": len(arguments.get("plan") or "")},
            )
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_advance_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        result = ude.advance_file(gate, arguments.get("path"))
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_file_status":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        return _json(ude.status_payload(gate))

    if name == "ultradeep_plan_refute":
        task_id = arguments["task_id"]
        result = ude.record_plan_refute(
            findings=arguments.get("findings") or [],
            search_queries=arguments.get("search_queries") or arguments.get("queries") or [],
            broken_steps=arguments.get("broken_steps"),
            decision=arguments.get("decision") or "HOLD",
        )
        store.update_metadata(task_id, {"ultradeep_plan_refute": result})
        if result.get("ok"):
            store.submit_evidence(
                task_id,
                EvidenceType.LOG,
                "ultradeep_plan_refute HOLD",
                {**result, "source": "ultradeep_plan_refute", "server_authored": True},
                server_authored=True,
            )
        return _json(result)

    if name == "ultradeep_repair_wake":
        from godkiller_mcp.repair_wake import (
            get_repair,
            merge_wake_into,
            record_repair_wake,
        )

        task_id = arguments["task_id"]
        state = store.get(task_id)
        meta = state.handle.metadata or {}
        plan_refute = meta.get("ultradeep_plan_refute") or {}
        plan_refute_ok = plan_refute.get("status") == "HOLD" and plan_refute.get("ok") is True
        wake = record_repair_wake(
            diagnosis=arguments.get("diagnosis") or "",
            hypotheses=arguments.get("hypotheses") or [],
            tools_tried=arguments.get("tools_tried"),
            touches_plan=bool(arguments.get("touches_plan", False)),
            plan_refute_ok=plan_refute_ok or bool(arguments.get("plan_refute_ok", False)),
            self_heal_used=bool(arguments.get("self_heal_used", False)),
        )
        merged = merge_wake_into(get_repair(meta), wake)
        if wake.get("ok"):
            # preserve streak from armed state until verify clears
            merged["streak"] = int(get_repair(meta).get("streak") or 0)
            merged["escalated"] = merged["streak"] >= 3
        store.update_metadata(task_id, {"repair_wake": merged})
        out = {**wake, "repair_wake": merged}
        if wake.get("ok"):
            store.submit_evidence(
                task_id,
                EvidenceType.LOG,
                "ultradeep_repair_wake",
                {**out, "source": "ultradeep_repair_wake", "server_authored": True},
                server_authored=True,
            )
        return _json(out)


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['list_modes', 'get_protocol', 'get_constitution', 'skill_catalog', 'record_skills_loaded', 'activate_mode', 'ultradeep_queue_files', 'ultradeep_think_file', 'ultradeep_plan_file', 'ultradeep_advance_file', 'ultradeep_file_status', 'ultradeep_plan_refute', 'ultradeep_repair_wake']:
        reg(tool, _entry)
