"""Claim armor: exit preflight + council refute-first.

Anti-hype: chat praise is not status. These gates force machine proof.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from godkiller_mcp.ship_mode import env_disables, relax_enabled


def claim_exit_preflight_gate(state) -> Tuple[bool, str]:
    """gk_verify.exit must have passed before claim_done."""
    if relax_enabled():
        return True, "exit_checklist skipped (DEV_RELAX)"
    for ev in reversed(list(getattr(state, "evidences", []) or [])):
        payload = ev.payload or {}
        if payload.get("source") != "exit_checklist":
            continue
        if payload.get("server_authored") is not True:
            continue
        if payload.get("directive") == "pass" and payload.get("status") == "ready":
            return True, "exit_checklist pass on record"
        return (
            False,
            f"exit_checklist not green (directive={payload.get('directive')}, "
            f"blocking={payload.get('blocking')}) — fix gates then gk_verify.exit again",
        )
    return (
        False,
        "Forced gate: call gk_verify.exit (exit_checklist) and get directive=pass "
        "before claim_done — do not declare done from chat",
    )


_HOLLOW_MUST_FIX = frozenset(
    {
        "nits",
        "nit",
        "typo",
        "typos",
        "lgtm",
        "ok",
        "fine",
        "none",
        "n/a",
        "na",
        "-",
        "minor",
        "style",
    }
)


def _substantial_must_fix(items: List[Any]) -> List[str]:
    out: List[str] = []
    for x in items or []:
        s = str(x).strip()
        if len(s) < 8:
            continue
        if s.lower() in _HOLLOW_MUST_FIX:
            continue
        out.append(s)
    return out


def _substantial_hacker_reject(op: Dict[str, Any]) -> bool:
    """REJECT counts only with non-hollow critique + substantial must_fix + severity."""
    from godkiller_mcp.evidence_quality import is_hollow_text

    if str(op.get("vote", "")).upper() != "REJECT":
        return False
    try:
        sev = int(op.get("severity") or 0)
    except Exception:
        sev = 0
    if sev < 5:
        return False
    critique = str(op.get("critique") or "")
    hollow, _ = is_hollow_text(critique, min_chars=24, min_unique_words=4)
    if hollow:
        return False
    if not _substantial_must_fix(op.get("must_fix") or []):
        return False
    return True


def _hacker_rejected(opinions: Dict[str, Any]) -> bool:
    """Real refute: substantial Hacker REJECT (not vote-only theatre)."""
    h = opinions.get("hacker") or {}
    return _substantial_hacker_reject(h if isinstance(h, dict) else {})


def _reject_seen_in_payload(payload: Dict[str, Any]) -> bool:
    """At least one substantial Hacker REJECT in final opinions or transcript."""
    if _hacker_rejected(payload.get("final_opinions") or {}):
        return True
    if _substantial_hacker_reject(payload.get("hacker") or {}):
        return True
    for entry in payload.get("transcript") or []:
        ops = entry.get("opinions") or entry
        if isinstance(ops, dict) and _hacker_rejected(ops):
            return True
    return False


def claim_council_gate(state) -> Tuple[bool, str]:
    """Refute-first council must PASS before claim — no rubber-stamp APPROVE."""
    if relax_enabled():
        return True, "council skipped (DEV_RELAX)"
    if env_disables("GODKILLER_COUNCIL"):
        return True, "council disabled (relax only)"

    from godkiller_mcp.ship_mode import profile

    for ev in reversed(list(getattr(state, "evidences", []) or [])):
        payload = ev.payload or {}
        if payload.get("source") != "council_finalize":
            continue
        if payload.get("server_authored") is not True:
            continue
        verdict = str(payload.get("verdict") or "")
        if verdict != "COUNCIL_PASS" or not payload.get("consensus_reached"):
            return (
                False,
                f"council verdict={verdict} — need COUNCIL_PASS (refute then unanimous approve)",
            )
        # Remaining substantial must_fix blocks claim
        open_fixes: List[str] = []
        for role in ("coder", "hacker", "optimizer"):
            op = payload.get(role) or (payload.get("final_opinions") or {}).get(role) or {}
            open_fixes.extend(_substantial_must_fix(op.get("must_fix") or []))
        if open_fixes:
            sample = "; ".join(open_fixes[:5])
            return False, f"council must_fix still open: {sample}"
        if not _reject_seen_in_payload(payload):
            return (
                False,
                "council refute-first failed: need substantial Hacker REJECT "
                "(critique≥24 non-hollow + must_fix + severity≥5) before COUNCIL_PASS",
            )
        # Host multi-seat = theatre_risk; PROFILE=ship rejects unless explicitly allowed
        allow_host = os.environ.get("GODKILLER_ALLOW_HOST_COUNCIL", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if (
            payload.get("theatre_risk")
            and str(payload.get("mode") or "").lower() == "host"
            and profile() == "ship"
            and not allow_host
        ):
            return (
                False,
                "council theatre_risk: host-mode seats are IDE-played — not ship armor. "
                "Use mode=api (LLM key) or set GODKILLER_ALLOW_HOST_COUNCIL=1 for local beta.",
            )
        note = "council COUNCIL_PASS with REJECT-then-approve on record"
        if payload.get("theatre_risk"):
            note += " (theatre_risk labeled — host seats)"
        return True, note

    return (
        False,
        "Forced gate: run gk_code.council → submit all roles "
        "(Hacker REJECT must have real critique+must_fix) "
        "→ council_finalize → COUNCIL_PASS before claim_done",
    )
