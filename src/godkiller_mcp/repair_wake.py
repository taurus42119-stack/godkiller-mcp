"""Repair wake — brain loop after verify/probe/hollow failure.

Keeps gk_code.self_heal as tool-fallback layer. This module forces
diagnosis + new hypotheses before the next edit_safe.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from godkiller_mcp.evidence_quality import dedupe_findings, is_hollow_text
from godkiller_mcp.ship_mode import env_disables, relax_enabled

MIN_HYPOTHESES = 3
ESCALATE_STREAK = 3


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_repair(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = metadata or {}
    r = meta.get("repair_wake")
    if not isinstance(r, dict):
        return {
            "required": False,
            "verify_pending": False,
            "streak": 0,
            "escalated": False,
            "history": [],
        }
    r.setdefault("required", False)
    r.setdefault("verify_pending", False)
    r.setdefault("streak", 0)
    r.setdefault("escalated", False)
    r.setdefault("history", [])
    return r


def mark_repair_required(
    metadata: Optional[Dict[str, Any]],
    *,
    reason: str,
    source: str,
) -> Dict[str, Any]:
    """Arm repair gate after a real failure. Returns new repair_wake blob."""
    r = get_repair(metadata)
    r["required"] = True
    r["verify_pending"] = False
    r["streak"] = int(r.get("streak") or 0) + 1
    r["last_reason"] = (reason or "failure")[:500]
    r["last_source"] = (source or "unknown")[:80]
    r["updated_at"] = _utcnow()
    if r["streak"] >= ESCALATE_STREAK:
        r["escalated"] = True
    hist = list(r.get("history") or [])
    hist.append(
        {
            "event": "armed",
            "source": r["last_source"],
            "reason": r["last_reason"],
            "streak": r["streak"],
            "at": _utcnow(),
        }
    )
    r["history"] = hist[-20:]
    return r


def clear_after_verify_pass(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """After green verify: clear pending; reset streak if wake was done."""
    r = get_repair(metadata)
    if r.get("required"):
        # Still need wake — do not clear
        return r
    if r.get("verify_pending"):
        r["verify_pending"] = False
        r["streak"] = 0
        r["escalated"] = False
        r["last_cleared_at"] = _utcnow()
        hist = list(r.get("history") or [])
        hist.append({"event": "cleared_by_verify", "at": _utcnow()})
        r["history"] = hist[-20:]
    return r


def require_repair_clear(metadata: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    """Block edits while repair is required."""
    if relax_enabled():
        return True, "repair_wake skipped (DEV_RELAX)"
    if env_disables("GODKILLER_REPAIR_WAKE"):
        return True, "repair_wake disabled (relax only)"
    r = get_repair(metadata)
    if not r.get("required"):
        return True, "repair not required"
    esc = ""
    if r.get("escalated"):
        esc = (
            " ESCALATED streak≥"
            f"{ESCALATE_STREAK}: run council/swarm attacker before retrying edits."
        )
    return (
        False,
        "Forced repair wake: call ultradeep_repair_wake "
        f"(diagnosis + ≥{MIN_HYPOTHESES} hypotheses) before edit_safe. "
        f"Armed by {r.get('last_source')}: {r.get('last_reason')}."
        f"{esc}",
    )


def record_repair_wake(
    *,
    diagnosis: str,
    hypotheses: Sequence[Any],
    tools_tried: Optional[Sequence[str]] = None,
    touches_plan: bool = False,
    plan_refute_ok: bool = False,
    self_heal_used: bool = False,
) -> Dict[str, Any]:
    """
    Single entrypoint validation. Does not mutate metadata itself —
    caller stores returned blob merged into repair_wake.
    """
    diag = (diagnosis or "").strip()
    hollow, why = is_hollow_text(diag, min_chars=40, min_unique_words=6)
    if hollow:
        return {
            "ok": False,
            "required": True,
            "reason": f"diagnosis hollow/too thin: {why}",
        }
    hyps: List[str] = []
    for h in hypotheses or []:
        if isinstance(h, dict):
            text = str(h.get("text") or h.get("hypothesis") or "").strip()
        else:
            text = str(h).strip()
        hollow_h, _ = is_hollow_text(text, min_chars=16, min_unique_words=3)
        if hollow_h:
            continue
        hyps.append(text[:400])
    hyps, dupes = dedupe_findings(hyps)
    if len(hyps) < MIN_HYPOTHESES:
        return {
            "ok": False,
            "required": True,
            "reason": (
                f"need ≥{MIN_HYPOTHESES} unique substantial hypotheses "
                f"(got {len(hyps)}, dupes={dupes})"
            ),
        }
    if touches_plan and not plan_refute_ok:
        return {
            "ok": False,
            "required": True,
            "reason": (
                "touches_plan=true requires ultradeep_plan_refute HOLD first "
                "(set plan_refute_ok after HOLD)"
            ),
        }
    return {
        "ok": True,
        "required": False,
        "verify_pending": True,
        "reason": "repair_wake OK — may edit once; must re-run verify_bundle to clear",
        "diagnosis": diag[:2000],
        "hypotheses": hyps[:10],
        "tools_tried": [str(t)[:80] for t in (tools_tried or [])][:20],
        "self_heal_used": bool(self_heal_used),
        "touches_plan": bool(touches_plan),
        "woke_at": _utcnow(),
        "source": "ultradeep_repair_wake",
        "server_authored": True,
    }


def merge_wake_into(existing: Dict[str, Any], wake: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a successful/failed wake result into repair state."""
    r = dict(existing or {})
    if not wake.get("ok"):
        r["required"] = True
        r["last_wake_error"] = wake.get("reason")
        r["updated_at"] = _utcnow()
        return r
    streak = int(r.get("streak") or 0)
    r.update(
        {
            "required": False,
            "verify_pending": True,
            "streak": streak,  # cleared only after verify pass
            "escalated": streak >= ESCALATE_STREAK,
            "last_wake": {
                "diagnosis": wake.get("diagnosis"),
                "hypotheses": wake.get("hypotheses"),
                "tools_tried": wake.get("tools_tried"),
                "self_heal_used": wake.get("self_heal_used"),
                "at": wake.get("woke_at"),
            },
            "updated_at": _utcnow(),
        }
    )
    hist = list(r.get("history") or [])
    hist.append({"event": "wake_ok", "at": _utcnow(), "hypotheses": len(wake.get("hypotheses") or [])})
    r["history"] = hist[-20:]
    return r
