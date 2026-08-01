"""Machine claim verdict — agent may propose done; system decides.

status=blocked means the turn must not be treated as finished.
Chat summary never overrides this object.
"""

from __future__ import annotations

import re
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
    "plan": "Validate 9-step plan (+ UI playtest phases if UI); keep edits inside plan envelope.",
    "fault_probe": "Tests too shallow (survivors) — deepen tests; rerun fault_probe.",
    "exit": "Call gk_verify.exit until directive=pass, then claim_done.",
    "council": "Run council with Hacker refute-first → finalize COUNCIL_PASS.",
    "swarm": "gk_code.swarm_spawn → submit all roles → swarm_collect (passed), then retry.",
    "handoff": "write_feedback(passed=true) after eval, then retry.",
    "search": "Record required search queries, then retry claim_done.",
    "skill": "Satisfy skill gate, then retry claim_done.",
    "tool_propose": "Propose 5–10 tools → approve or reject_all → tool_used if approved.",
    "quality": "Raise quality/competitor/ladder evidence, then retry.",
    "ui_proof": "Run app → gk_evidence.visual_step (~10 step_ids) with expected_elements → GREEN critics → retry.",
    "phase_close": "Legal phase path to CLAIM_DONE required before close.",
}


KNOWN_GATE_TOKENS = frozenset(LAYER.keys())


def classify_from_reason(reason: str, *, gate: Optional[str] = None) -> str:
    """Prefer server gate tokens; substring match is last-resort for legacy reasons."""
    if gate and gate in KNOWN_GATE_TOKENS and gate != "ok":
        return gate
    r_raw = reason or ""
    m = re.search(r"gate[=:]([a-z_]+)", r_raw, flags=re.I)
    if m:
        tok = m.group(1).lower()
        if tok in KNOWN_GATE_TOKENS and tok != "ok":
            return tok
        # aliases sometimes minted in prose
        aliases = {
            "exit_checklist": "exit",
            "hollow_surface": "hollow",
            "plan_lock": "plan",
        }
        if tok in aliases:
            return aliases[tok]

    r = r_raw.lower()
    # Prefer stable machine phrases minted by this package
    token_phrases = (
        ("already closed", "closed"),
        ("material_hash", "freshness"),
        ("fault_probe", "fault_probe"),
        ("exit_checklist", "exit"),
        ("verify_bundle", "verify"),
        ("blast_radius", "blast_radius"),
        ("hollow_surface", "hollow"),
        ("tool_propose", "tool_propose"),
        ("council", "council"),
    )
    for needle, tok in token_phrases:
        if needle in r:
            return tok

    if "stale" in r:
        return "freshness"
    if "survivor" in r:
        return "fault_probe"
    if "gk_verify.exit" in r:
        return "exit"
    if "refute-first" in r:
        return "council"
    if "hollow" in r:
        return "hollow"
    if "plan" in r and ("lock" in r or "validate" in r or "envelope" in r or "9-step" in r):
        return "plan"
    if "result_digest" in r:
        return "verify"
    if "must reach verify" in r or "verify phase" in r:
        return "phase"
    if "rubric" in r:
        return "rubric"
    if "ui_journey" in r or "screenshot" in r or "ui proof" in r or "visual sequence" in r:
        return "ui_proof"
    if "feedback" in r or "handoff" in r:
        return "handoff"
    if "search" in r:
        return "search"
    if "skill" in r:
        return "skill"
    if "tool_approve" in r or "tool_used" in r or "silent install" in r:
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
    detail: bool = False,
    stage_board: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Structured claim response — status is authoritative.

    Compact by default (token-cheap). detail=True keeps long mouth/graph.
    """
    from godkiller_mcp.compact_io import verbose_enabled

    detail = verbose_enabled(detail)
    if allowed:
        g = "ok"
    elif gate and gate in KNOWN_GATE_TOKENS:
        g = gate
    else:
        g = classify_from_reason(reason, gate=gate)
    status = "done" if allowed else "blocked"
    out: Dict[str, Any] = {
        "status": status,
        "allowed": allowed,
        "gate": g,
        "layer": LAYER.get(g, g),
        "reason": reason,
        "action": action,
        "verdict": "DONE" if allowed else "NOT_DONE",
    }
    if not allowed:
        out["next"] = NEXT_ACTION.get(g, "Fix blocking gate, re-prove, retry claim_done.")
        # Mini board when we only know the blocking gate
        out["stage_board"] = stage_board or {
            "passed": [],
            "failed": [{"gate": g, "detail": reason}],
            "remaining": [g],
            "current": g,
            "score": "blocked",
            "confirm": f"NOT CONFIRMED — failed stage [{g}]. Clear it, then re-verify/exit.",
        }
    else:
        out["stage_board"] = stage_board or {
            "passed": ["claim"],
            "failed": [],
            "remaining": [],
            "current": None,
            "score": "done",
            "confirm": "CONFIRMED — all required stages clear. Task may report done.",
        }
    if detail:
        out["agent_role"] = {
            "may_propose_done": True,
            "may_decide_done": False,
            "chat_summary_is_not_status": True,
            "narrate_from_stage_board": True,
        }
        out["honest_mouth"] = (
            "This JSON is authoritative for claim_done. "
            "Chat narration cannot override status/gate. "
            "Narrate progress from stage_board only."
        )
        if allowed:
            out["next"] = "Task closed by harness — chat may report done only after this status."
    if results is not None:
        # Compact: keep pass/fail summaries, not full dumps unless detail
        if detail:
            out["results"] = [
                r.model_dump() if hasattr(r, "model_dump") else r for r in results
            ]
        else:
            slim = []
            for r in results:
                d = r.model_dump() if hasattr(r, "model_dump") else (r if isinstance(r, dict) else {"value": r})
                if isinstance(d, dict):
                    slim.append(
                        {
                            k: d[k]
                            for k in ("id", "name", "passed", "ok", "gate", "summary", "reason")
                            if k in d
                        }
                        or d
                    )
                else:
                    slim.append(d)
            out["results"] = slim
    if graph is not None and detail:
        out["graph"] = graph
    elif graph is not None and not allowed:
        # One-line blocker only
        blocked = graph.get("blocked") if isinstance(graph, dict) else None
        reason_g = graph.get("reason") if isinstance(graph, dict) else None
        out["blocked"] = blocked if blocked is not None else True
        if reason_g and reason_g != reason:
            out["graph_reason"] = reason_g
    return out
