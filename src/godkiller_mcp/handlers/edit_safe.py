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
    if name == "get_failing_slice":
        report = get_failing_slice(arguments["test_output"], arguments.get("workspace"))
        out: Dict[str, Any] = report.to_evidence_payload()
        if arguments.get("attach", True) and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.FAILING_SLICE,
                summary=report.summary,
                payload=report.to_evidence_payload(),
                server_authored=True,
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError as exc:
                out["phase_error"] = str(exc)
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "blast_radius":
        report = blast_radius(arguments["symbol"], arguments["workspace"])
        out = report.to_evidence_payload()
        if arguments.get("attach", True) and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.BLAST_RADIUS,
                summary=report.summary,
                payload={**report.to_evidence_payload(), "server_authored": True},
                server_authored=True,
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError as exc:
                out["phase_error"] = str(exc)
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "check_edit_safe":
        task_id = arguments.get("task_id")
        if task_id:
            from godkiller_mcp.governance import plan_always_required

            state = store.get(task_id)
            require_plan = arguments.get("require_plan")
            if require_plan is None:
                require_plan = plan_always_required() or state.handle.phase.value in (
                    "fix",
                    "verify",
                    "claim_done",
                )
            if require_plan:
                plan_meta = (state.handle.metadata or {}).get("plan_validation")
                if not plan_meta or not plan_meta.get("valid"):
                    plan_dict = (state.handle.metadata or {}).get("plan_dict")
                    if plan_dict:
                        plan_meta = plan_os.validate(plan_dict)
                        store.update_metadata(task_id, {"plan_validation": plan_meta})
                    if not plan_meta or not plan_meta.get("valid"):
                        return _json(
                            {
                                "allowed": False,
                                "safe": False,
                                "reason": "write-through-plan: 9-step plan missing/incomplete — gk_meta.plan_validate first",
                                "action": PolicyAction.BLOCK.value,
                            }
                        )
                ok_pr, reason_pr = ude.require_plan_refute_hold(state.handle.metadata)
                if not ok_pr:
                    return _json(
                        {
                            "allowed": False,
                            "safe": False,
                            "reason": reason_pr,
                            "action": PolicyAction.BLOCK.value,
                        }
                    )
            from godkiller_mcp.repair_wake import require_repair_clear

            ok_rw, reason_rw = require_repair_clear(state.handle.metadata)
            if not ok_rw:
                return _json(
                    {
                        "allowed": False,
                        "safe": False,
                        "reason": reason_rw,
                        "action": PolicyAction.BLOCK.value,
                        "repair_wake": (state.handle.metadata or {}).get("repair_wake"),
                    }
                )
            from godkiller_mcp.swarm import require_swarm_before_edit

            ok_sw, reason_sw = require_swarm_before_edit(state)
            if not ok_sw:
                return _json(
                    {
                        "allowed": False,
                        "safe": False,
                        "reason": reason_sw,
                        "action": PolicyAction.BLOCK.value,
                    }
                )
            from godkiller_mcp.debug_engine import require_self_ctf_before_fix

            ok_ctf, reason_ctf = require_self_ctf_before_fix(state)
            if not ok_ctf:
                return _json(
                    {
                        "allowed": False,
                        "safe": False,
                        "reason": reason_ctf,
                        "action": PolicyAction.BLOCK.value,
                    }
                )
        if task_id and arguments.get("require_blast", True):
            state = store.get(task_id)
            ok_b, reason_b = require_blast_before_edit(state.evidence_types())
            if not ok_b:
                loops.record(task_id, "check_edit_safe", signature="edit_blocked_no_blast", phase=state.handle.phase)
                return _json(
                    {
                        "allowed": False,
                        "safe": False,
                        "reason": reason_b,
                        "action": PolicyAction.BLOCK.value,
                    }
                )
        report = check_edit_safe(arguments["paths"], arguments["workspace"])
        out = report.to_evidence_payload()
        if not out.get("safe", False):
            return _json(
                {
                    "allowed": False,
                    "safe": False,
                    "reason": "; ".join(out.get("reasons") or ["unsafe paths"]),
                    "action": PolicyAction.BLOCK.value,
                    **out,
                }
            )
        out["allowed"] = True
        # Additive /ultradeep per-file gate (opt-out: require_per_file_gate=false)
        if task_id and arguments.get("require_per_file_gate", True):
            state = store.get(task_id)
            gate = ude.get_gate(state.handle.metadata)
            if gate.get("enabled"):
                ok_f, reason_f = ude.check_edit_paths(gate, arguments["paths"])
                if not ok_f:
                    loops.record(task_id, "check_edit_safe", signature="edit_blocked_per_file", phase=state.handle.phase)
                    return _json(
                        {
                            "allowed": False,
                            "safe": False,
                            "reason": reason_f,
                            "action": PolicyAction.BLOCK.value,
                            "file_gate": ude.status_payload(gate),
                        }
                    )
                out["file_gate"] = reason_f
        if arguments.get("attach", True) and task_id:
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.EDIT_SAFE,
                summary=report.summary,
                payload={**report.to_evidence_payload(), "server_authored": True},
                server_authored=True,
            )
            out["evidence_id"] = ev.id
            loops.record(task_id, "check_edit_safe", signature="check_edit_safe:" + ",".join(arguments["paths"][:3]))
        return _json(out)


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['get_failing_slice', 'blast_radius', 'check_edit_safe']:
        reg(tool, _entry)
