"""Domain handlers peeled from dispatch (facade names unchanged)."""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.types import TextContent


async def handle(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    from godkiller_mcp.dispatch import (
        _json,
        store,
        policy,
        loops,
        verify_runner,
        lessons,
        handoff,
        browser,
        vision,
        marathon,
        modes,
        workflow,
        plan_os,
        STATE_ROOT,
        STORE_DIR,
    )
    from godkiller_mcp.schema import EvidenceType, Phase, PolicyAction, TaskKind
    from godkiller_mcp.policy import rubric_for_kind
    import asyncio
    from pathlib import Path

    arguments = arguments or {}
    from godkiller_mcp.governance import missing_arg_error

    if name == "open_task":
        bad = missing_arg_error(arguments, "kind", "goal")
        if bad:
            return _json(bad)
        state = store.open_task(
            kind=arguments["kind"],
            goal=arguments["goal"],
            project_id=arguments.get("project_id", "default"),
        )
        rubric = [
            {"id": r.id, "description": r.description}
            for r in rubric_for_kind(state.handle.kind)
        ]
        return _json(
            {
                "task_id": state.handle.task_id,
                "kind": state.handle.kind.value,
                "phase": state.handle.phase.value,
                "rubric_id": state.handle.rubric_id,
                "rubric": rubric,
                "goal": state.handle.goal,
            }
        )

    if name == "propose_hypothesis":
        from godkiller_mcp.search_gates import assert_phase_search_gate

        bad = missing_arg_error(arguments, "task_id", "claim")
        if bad:
            return _json(bad)
        hyp = store.propose_hypothesis(
            task_id=arguments["task_id"],
            claim=arguments["claim"],
            support_refs=arguments.get("support_refs"),
            refute_refs=arguments.get("refute_refs"),
        )
        cur = store.get(arguments["task_id"])
        ok_s, reason_s = assert_phase_search_gate(cur, Phase.HYPOTHESIZE)
        if ok_s:
            try:
                store.assert_phase(arguments["task_id"], Phase.HYPOTHESIZE)
            except ValueError as exc:
                return _json(
                    {
                        **hyp.model_dump(),
                        "phase_advanced": False,
                        "phase_error": str(exc),
                    }
                )
        else:
            return _json(
                {
                    **hyp.model_dump(),
                    "phase_advanced": False,
                    "phase_blocked": reason_s,
                }
            )
        return _json({**hyp.model_dump(), "phase_advanced": True})

    if name == "assert_phase":
        from godkiller_mcp.search_gates import assert_phase_search_gate
        from godkiller_mcp.skill_gates import assert_phase_skill_gate

        bad = missing_arg_error(arguments, "task_id", "phase")
        if bad:
            return _json(bad)
        cur = store.get(arguments["task_id"])
        ok_s, reason_s = assert_phase_search_gate(cur, arguments["phase"])
        if not ok_s:
            return _json(
                {
                    "allowed": False,
                    "reason": reason_s,
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
        ok_sk, reason_sk = assert_phase_skill_gate(cur, arguments["phase"])
        if not ok_sk:
            return _json(
                {
                    "allowed": False,
                    "reason": reason_sk,
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
        try:
            state = store.assert_phase(arguments["task_id"], arguments["phase"])
        except ValueError as exc:
            return _json(
                {
                    "allowed": False,
                    "reason": str(exc),
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
        loops.note_phase_advance(arguments["task_id"], arguments["phase"])
        loops.record(
            arguments["task_id"],
            "assert_phase",
            signature=f"assert_phase:{arguments['phase']}",
            phase=arguments["phase"],
        )
        return _json(
            {
                "allowed": True,
                "task_id": state.handle.task_id,
                "phase": state.handle.phase.value,
            }
        )

    if name == "submit_evidence":
        from godkiller_mcp.search_gates import normalize_web_search_payload

        bad = missing_arg_error(arguments, "task_id", "type", "summary")
        if bad:
            return _json(bad)
        payload = arguments.get("payload") or {}
        if isinstance(payload, dict):
            payload = normalize_web_search_payload(payload)
        try:
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=arguments["type"],
                summary=arguments["summary"],
                payload=payload,
                uri=arguments.get("uri"),
                contradicts=arguments.get("contradicts"),
                server_authored=False,
            )
        except PermissionError as exc:
            return _json(
                {
                    "allowed": False,
                    "error": str(exc),
                    "action": PolicyAction.BLOCK.value,
                }
            )
        # Mirror queries into task metadata for durable gate checks
        queries = (payload or {}).get("queries") if isinstance(payload, dict) else None
        if queries:
            existing = list((store.get(arguments["task_id"]).handle.metadata or {}).get("search_queries") or [])
            merged = list(dict.fromkeys([*existing, *[str(q) for q in queries if str(q).strip()]]))
            store.update_metadata(arguments["task_id"], {"search_queries": merged})
        return _json(ev.model_dump())

    if name == "evaluate_rubric":
        state = store.get(arguments["task_id"])
        results = policy.evaluate_rubric(state)
        return _json(
            {
                "task_id": state.handle.task_id,
                "all_passed": policy.all_passed(results),
                "results": [r.model_dump() for r in results],
            }
        )

    if name == "request_claim_done":

        from godkiller_mcp.claim_verdict import build_claim_payload

        bad = missing_arg_error(arguments, "task_id")
        if bad:
            return _json(bad)
        state = store.get(arguments["task_id"])
        if state.closed:
            return _json(
                build_claim_payload(
                    allowed=False,
                    reason="Task is already closed.",
                    gate="closed",
                    action=PolicyAction.BLOCK.value,
                )
            )
        loops.record(
            arguments["task_id"],
            "request_claim_done",
            signature="request_claim_done",
            phase=state.handle.phase,
        )
        # Feature UI gate
        if state.handle.kind == TaskKind.FEATURE:
            ok_ui, reason_ui = browser.require_ui_proof_for_feature(state.handle.task_id)
            if not ok_ui:
                blocked = workflow.what_blocked_claim_done(state.handle.task_id, reason_ui)
                return _json(
                    build_claim_payload(
                        allowed=False,
                        reason=reason_ui,
                        gate="ui_proof",
                        action=PolicyAction.BLOCK.value,
                        graph=blocked,
                    )
                )
        handoff_ok = None
        handoff_reason = ""
        if arguments.get("handoff_slug"):
            handoff_ok, handoff_reason = handoff.require_passing_feedback(arguments["handoff_slug"])
        from godkiller_mcp.ship_mode import relax_enabled, ship_mode

        # Ship / armor: ignore client attempts to turn gates off or drop ladder
        if not relax_enabled():
            require_vb = True
            require_quality = True
            require_competitor = True
            ladder = "L1_presence"
        else:
            require_vb = bool(arguments.get("require_verify_bundle", True))
            require_quality = bool(arguments.get("require_quality_loop", True))
            require_competitor = bool(arguments.get("require_competitor_loop", True))
            ladder = arguments.get("min_ambition_ladder") or "L1_presence"
        if ship_mode() and not relax_enabled():
            # Floor ladder — client cannot lower below L1
            ladder = arguments.get("min_ambition_ladder") or "L1_presence"
            if not ladder or ladder.startswith("L0"):
                ladder = "L1_presence"
        allowed, results, reason, gate = policy.request_claim_done(
            state,
            require_verify_bundle=require_vb,
            handoff_feedback_ok=handoff_ok,
            handoff_reason=handoff_reason,
            require_quality_loop=require_quality,
            require_competitor_loop=require_competitor,
            min_ambition_ladder=ladder,
        )
        if allowed:
            try:
                if state.handle.phase != Phase.CLAIM_DONE:
                    store.assert_phase(state.handle.task_id, Phase.CLAIM_DONE)
                    loops.note_phase_advance(state.handle.task_id, Phase.CLAIM_DONE)
            except ValueError as exc:
                return _json(
                    build_claim_payload(
                        allowed=False,
                        reason=f"Cannot close: {exc}",
                        gate="phase_close",
                        action=PolicyAction.BLOCK.value,
                        results=results,
                    )
                )
            store.mark_closed(state.handle.task_id)
            state.last_policy_action = PolicyAction.ALLOW_CLAIM_DONE
            try:
                from godkiller_mcp.session_ledger import append_ledger

                append_ledger(
                    "claim_done",
                    {"allowed": True, "status": "done", "gate": "ok", "reason": reason},
                    task_id=state.handle.task_id,
                )
            except Exception:
                pass
        else:
            state.last_policy_action = PolicyAction.BLOCK
            state.failure_streak += 1
            try:
                from godkiller_mcp.session_ledger import append_ledger

                append_ledger(
                    "claim_done_blocked",
                    {
                        "allowed": False,
                        "status": "blocked",
                        "gate": gate,
                        "reason": reason,
                    },
                    task_id=state.handle.task_id,
                )
            except Exception:
                pass
        graph = None
        stage_board = None
        if not allowed:
            graph = workflow.what_blocked_claim_done(state.handle.task_id, reason)
            # Prefer the latest exit_checklist board for stage progress.
            for ev in reversed(state.evidence):
                payload = ev.payload or {}
                if str(payload.get("source") or "") != "exit_checklist":
                    continue
                if isinstance(payload.get("stage_board"), dict):
                    stage_board = payload["stage_board"]
                    break
                break
        return _json(
            build_claim_payload(
                allowed=allowed,
                reason=reason,
                gate=gate,
                results=results,
                graph=graph,
                action=state.last_policy_action.value if state.last_policy_action else None,
                stage_board=stage_board,
            )
        )

    if name == "policy_decide":
        state = store.get(arguments["task_id"])
        action = policy.decide(state)
        state.last_policy_action = action
        return _json({"task_id": state.handle.task_id, "action": action.value, "phase": state.handle.phase.value})

    if name == "get_task_graph":
        return _json(store.dump_graph(arguments["task_id"]))


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['open_task', 'propose_hypothesis', 'assert_phase', 'submit_evidence', 'evaluate_rubric', 'request_claim_done', 'policy_decide', 'get_task_graph']:
        reg(tool, _entry)
