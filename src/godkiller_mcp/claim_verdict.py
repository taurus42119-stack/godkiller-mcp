"""Machine claim verdict — agent may propose done; system decides.

status=blocked means the turn must not be treated as finished.
Chat summary never overrides this object.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

# Human-facing layer names aligned with the three-anger model + supporting gates
LAYER = {
    "ok": "done",
    "closed": "closed",
    "phase": "phase",
    "rubric": "rubric",
    "blast_radius": "blast_radius",
    "verify": "verify",  # self-report / terminal trust
    "freshness": "freshness",  # edit-after-test
    "hollow": "hollow_surface",
    "plan": "plan_lock",
    "fault_probe": "fault_probe",  # shallow green
    "exit": "exit_checklist",
    "council": "council",
    "swarm": "swarm",
    "handoff": "handoff",
    "search": "search",
    "skill": "skill",
    "tool_propose": "tool_propose",
    "quality": "quality",
    "ui_proof": "ui_proof",
    "phase_close": "phase",
}

NEXT_ACTION: Dict[str, str] = {
    "closed": "Open a new task — this one is already closed.",
    "phase": "Advance to VERIFY (assert_phase) then retry claim_done.",
    "rubric": "Submit missing rubric evidence, then retry claim_done.",
    "blast_radius": "Call blast_radius before editing; record evidence; retry.",
    "verify": "Run server verify_bundle (disk + digest); do not paste terminal text.",
    "freshness": "Code changed after verify — rerun verify_bundle and fault_probe.",
    "hollow": "Remove placeholders / unfinished bodies; re-verify; retry.",
    "plan": "Validate 9-step plan; keep edits inside plan envelope.",
    "fault_probe": "Tests too shallow (survivors) — deepen tests; rerun fault_probe.",
    "exit": "Call gk_verify.exit until directive=pass, then claim_done.",
    "council": "Run council with Hacker refute-first → finalize COUNCIL_PASS.",
    "swarm": "gk_code.swarm_spawn → submit all roles → swarm_collect (passed), then retry.",
    "handoff": "write_feedback(passed=true) after eval, then retry.",
    "search": "Record required search queries, then retry claim_done.",
    "skill": "Satisfy skill gate, then retry claim_done.",
    "tool_propose": "Propose 5–10 tools → approve or reject_all → tool_used if approved.",
    "quality": "Raise quality/competitor/ladder evidence, then retry.",
    "ui_proof": "Submit UI_JOURNEY or SCREENSHOT evidence, then retry.",
    "phase_close": "Legal phase path to CLAIM_DONE required before close.",
}


def classify_from_reason(reason: str) -> str:
    """Fallback classifier when gate id was not threaded."""
    r = (reason or "").lower()
    if "already closed" in r:
        return "closed"
    if "stale" in r or "material_hash" in r:
        return "freshness"
    if "fault_probe" in r or "survivor" in r:
        return "fault_probe"
    if "exit_checklist" in r or "gk_verify.exit" in r:
        return "exit"
    if "council" in r or "refute-first" in r:
        return "council"
    if "hollow" in r:
        return "hollow"
    if "plan" in r and ("lock" in r or "validate" in r or "envelope" in r or "9-step" in r):
        return "plan"
    if "verify_bundle" in r or "result_digest" in r:
        return "verify"
    if "blast_radius" in r:
        return "blast_radius"
    if "verify phase" in r or "must reach verify" in r:
        return "phase"
    if "rubric" in r:
        return "rubric"
    if "ui_journey" in r or "screenshot" in r or "ui proof" in r:
        return "ui_proof"
    if "feedback" in r or "handoff" in r:
        return "handoff"
    if "search" in r:
        return "search"
    if "skill" in r:
        return "skill"
    if "tool_propose" in r or "tool_approve" in r or "tool_used" in r or "silent install" in r:
        return "tool_propose"
    if "quality" in r or "competitor" in r or "ambition" in r or "ladder" in r:
        return "quality"
    if "cannot close" in r or "phase" in r:
        return "phase_close"
    return "verify"


def build_claim_payload(
    *,
    allowed: bool,
    reason: str,
    gate: Optional[str] = None,
    results: Optional[Sequence[Any]] = None,
    graph: Optional[Dict[str, Any]] = None,
    action: Optional[str] = None,
) -> Dict[str, Any]:
    """Structured claim response — status is authoritative."""
    g = gate or ("ok" if allowed else classify_from_reason(reason))
    if allowed:
        g = "ok"
    status = "done" if allowed else "blocked"
    out: Dict[str, Any] = {
        "status": status,
        "allowed": allowed,
        "gate": g,
        "layer": LAYER.get(g, g),
        "reason": reason,
        "action": action,
        # Contract: agent proposes; harness decides
        "agent_role": {
            "may_propose_done": True,
            "may_decide_done": False,
            "chat_summary_is_not_status": True,
        },
    }
    if not allowed:
        out["next"] = NEXT_ACTION.get(g, "Fix the blocking gate, re-prove on disk, retry claim_done.")
        out["verdict"] = "NOT_DONE"
    else:
        out["next"] = "Task closed by harness — chat may report done only after this status."
        out["verdict"] = "DONE"
    if results is not None:
        out["results"] = [
            r.model_dump() if hasattr(r, "model_dump") else r for r in results
        ]
    if graph is not None:
        out["graph"] = graph
    return out
