"""Exit checklist — fail-closed preflight before claim_done (agent-gate style).

Directive: pass | reject. Missing proof is not proof.
Chat summary never overrides this object.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from godkiller_mcp.schema import EvidenceType, Phase, TaskKind, TaskState
from godkiller_mcp.ship_mode import profile_label, ship_mode


def _gate(name: str, ok: bool, detail: str) -> Dict[str, Any]:
    return {"gate": name, "ok": ok, "detail": detail}


def build_exit_checklist(
    state: TaskState,
    *,
    workspace: Optional[str] = None,
    require_blast_radius: bool = True,
    require_verify_bundle: bool = True,
    require_quality_loop: bool = True,
    require_competitor_loop: bool = True,
    min_ambition_ladder: str = "L1_presence",
) -> Dict[str, Any]:
    """Evaluate every claim armor layer without closing the task."""
    from godkiller_mcp.fault_probe import claim_fault_probe_gate
    from godkiller_mcp.governance import require_valid_plan
    from godkiller_mcp.hollow_surface import claim_hollow_gate
    from godkiller_mcp.policy import PolicyEngine
    from godkiller_mcp.quality_gates import quality_claim_gates
    from godkiller_mcp.search_gates import claim_search_gate
    from godkiller_mcp.skill_gates import claim_skill_gate
    from godkiller_mcp.verify_bundle import task_has_passing_verify_bundle

    if ship_mode():
        require_blast_radius = True
        require_verify_bundle = True
        require_quality_loop = True
        require_competitor_loop = True

    gates: List[Dict[str, Any]] = []
    blocking: List[str] = []

    if state.closed:
        g = _gate("closed", False, "Task already closed")
        gates.append(g)
        blocking.append("closed")
        return _pack(gates, blocking)

    engine = PolicyEngine()
    results = engine.evaluate_rubric(state)
    rub_ok = engine.all_passed(results)
    detail = "rubric OK" if rub_ok else "; ".join(
        f"{r.item_id}: {r.reason}" for r in results if not r.passed
    )
    gates.append(_gate("rubric", rub_ok, detail))
    if not rub_ok:
        blocking.append("rubric")

    phase_ok = Phase.VERIFY in state.phase_history or state.handle.phase == Phase.VERIFY
    gates.append(
        _gate("phase", phase_ok, "VERIFY reached" if phase_ok else "Must reach VERIFY")
    )
    if not phase_ok:
        blocking.append("phase")

    if require_blast_radius and state.handle.kind in (TaskKind.BUGFIX, TaskKind.REFACTOR):
        blast_ok = EvidenceType.BLAST_RADIUS in state.evidence_types()
        gates.append(
            _gate(
                "blast_radius",
                blast_ok,
                "blast_radius present" if blast_ok else "blast_radius evidence missing",
            )
        )
        if not blast_ok:
            blocking.append("blast_radius")

    if require_verify_bundle:
        ok_v, reason_v = task_has_passing_verify_bundle(state)
        gate_name = (
            "freshness"
            if (not ok_v and ("stale" in reason_v.lower() or "material_hash" in reason_v.lower()))
            else "verify"
        )
        gates.append(_gate(gate_name, ok_v, reason_v))
        if not ok_v:
            blocking.append(gate_name)

    ok_h, reason_h, _ = claim_hollow_gate(state)
    gates.append(_gate("hollow", ok_h, reason_h))
    if not ok_h:
        blocking.append("hollow")

    ok_p, reason_p = require_valid_plan(state)
    gates.append(_gate("plan", ok_p, reason_p))
    if not ok_p:
        blocking.append("plan")

    ok_f, reason_f = claim_fault_probe_gate(state, workspace=workspace)
    gates.append(_gate("fault_probe", ok_f, reason_f))
    if not ok_f:
        blocking.append("fault_probe")

    # Council is required for exit_checklist readiness (exit_preflight itself is NOT checked here)
    from godkiller_mcp.claim_armor import claim_council_gate

    ok_c, reason_c = claim_council_gate(state)
    gates.append(_gate("council", ok_c, reason_c))
    if not ok_c:
        blocking.append("council")

    from godkiller_mcp.swarm import claim_swarm_gate

    ok_sw, reason_sw = claim_swarm_gate(state)
    gates.append(_gate("swarm", ok_sw, reason_sw))
    if not ok_sw:
        blocking.append("swarm")

    ok_s, reason_s = claim_search_gate(state)
    gates.append(_gate("search", ok_s, reason_s))
    if not ok_s:
        blocking.append("search")

    ok_sk, reason_sk = claim_skill_gate(state)
    gates.append(_gate("skill", ok_sk, reason_sk))
    if not ok_sk:
        blocking.append("skill")

    from godkiller_mcp.tool_propose import claim_tool_propose_gate

    ok_tp, reason_tp = claim_tool_propose_gate(state)
    gates.append(_gate("tool_propose", ok_tp, reason_tp))
    if not ok_tp:
        blocking.append("tool_propose")

    from godkiller_mcp.roi_gates import claim_write_guard_gate

    ok_wg, reason_wg = claim_write_guard_gate()
    gates.append(_gate("write_guard", ok_wg, reason_wg))
    if not ok_wg:
        blocking.append("write_guard")

    ok_q, reason_q = quality_claim_gates(
        state,
        require_for_feature=require_quality_loop,
        require_competitor_loop=require_competitor_loop,
        min_ladder=min_ambition_ladder,
    )
    gates.append(_gate("quality", ok_q, reason_q))
    if not ok_q:
        blocking.append("quality")

    packed = _pack(gates, blocking)
    if "write_guard" in blocking:
        packed["next"] = (
            "Wire PreToolUse → godkiller-write-guard, live deny/allow, then "
            "GODKILLER_WRITE_GUARD_PROVEN=1 (PROFILE=ship)."
        )
    elif "tool_propose" in blocking:
        packed["next"] = (
            "Forced tool_propose: host-search → gk_mode.tool_propose (5–10) → "
            "tool_approve OR tool_reject_all → tool_used if approved — then re-run exit."
        )
    elif packed.get("directive") == "reject":
        meta = getattr(getattr(state, "handle", None), "metadata", None) or {}
        if not (meta.get("tool_propose") or {}).get("candidates"):
            packed["suggested_next_tools"] = [
                "tool_propose",
                "tool_approve",
                "tool_used",
            ]
    return packed


def _pack(gates: List[Dict[str, Any]], blocking: List[str]) -> Dict[str, Any]:
    passed = len(blocking) == 0
    cleared = [g["gate"] for g in gates if g.get("ok")]
    failed = [
        {"gate": g["gate"], "detail": g.get("detail") or ""}
        for g in gates
        if not g.get("ok")
    ]
    # Prefer stable order from gates list for remaining
    remaining = [g["gate"] for g in gates if not g.get("ok")]
    current = remaining[0] if remaining else None
    total = len(gates)
    n_ok = len(cleared)
    board = {
        "passed": cleared,
        "failed": failed,
        "remaining": remaining,
        "current": current,
        "score": f"{n_ok}/{total}",
        "confirm": (
            f"CONFIRMED {n_ok}/{total} clear. "
            + (
                "ALL STAGES PASS — may claim_done."
                if passed
                else (
                    f"FAILED: {', '.join(remaining)}. "
                    f"NEXT STAGE: {current}. "
                    f"LEFT: {' → '.join(remaining)}."
                )
            )
        ),
    }
    return {
        "status": "ready" if passed else "blocked",
        "directive": "pass" if passed else "reject",
        "profile": profile_label(),
        "ship_mode": ship_mode(),
        "blocking": blocking,
        "gates": gates,
        "stage_board": board,
        "agent_role": {
            "may_propose_done": True,
            "may_decide_done": False,
            "chat_summary_is_not_status": True,
            "narrate_from_stage_board": True,
        },
        "next": (
            "All armor layers green — you may call claim_done."
            if passed
            else (
                f"Clear stage [{current}] first "
                f"({board['score']} done). Remaining: {' → '.join(remaining)}."
            )
        ),
    }
