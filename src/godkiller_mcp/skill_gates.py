"""Forced skill look-then-choose — blocks overconfident skip.

Anti often thinks "I know enough" and never calls skill_catalog / never
view_file. These gates require catalog evidence + recorded loads (≤4).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from godkiller_mcp.schema import Phase, TaskKind, TaskState

PHASES_NEED_CATALOG = {
    Phase.HYPOTHESIZE,
    Phase.LOCALIZE,
    Phase.FIX,
    Phase.VERIFY,
    Phase.CLAIM_DONE,
}

PHASES_NEED_LOADED = {
    Phase.FIX,
    Phase.VERIFY,
    Phase.CLAIM_DONE,
}

BUGFIX_NEED_CATALOG = {Phase.FIX, Phase.VERIFY, Phase.CLAIM_DONE}


def _latest_skill_catalog(state: TaskState) -> Optional[dict]:
    for ev in reversed(state.evidence):
        payload = ev.payload or {}
        if payload.get("source") == "skill_catalog":
            return payload
    meta = state.handle.metadata or {}
    if meta.get("skill_catalog_query") is not None or meta.get("skill_scan_at"):
        return {
            "source": "skill_catalog",
            "query": meta.get("skill_catalog_query") or "",
            "shortlist_paths": meta.get("skill_catalog_shortlist") or [],
        }
    return None


def skills_loaded(state: TaskState) -> List[str]:
    meta = state.handle.metadata or {}
    raw = meta.get("skills_loaded") or []
    if isinstance(raw, str):
        raw = [raw]
    out: List[str] = []
    for p in raw:
        s = str(p).strip()
        if s and s not in out:
            out.append(s)
    for ev in state.evidence:
        payload = ev.payload or {}
        if payload.get("source") == "skills_loaded":
            for p in payload.get("paths") or []:
                s = str(p).strip()
                if s and s not in out:
                    out.append(s)
    return out


def catalog_gate(state: TaskState) -> tuple[bool, str]:
    hit = _latest_skill_catalog(state)
    if not hit:
        return (
            False,
            "Forced skill scan: call skill_catalog(query=goal, task_id=...) before proceeding. "
            "FORBIDDEN excuse: 'I already know enough' / training memory / activate_mode shortlist alone. "
            "Look-then-choose requires a real catalog call.",
        )
    return True, "skill_catalog recorded."


def loaded_gate(state: TaskState, *, min_loaded: int = 1, max_loaded: int = 4) -> tuple[bool, str]:
    paths = skills_loaded(state)
    n = len(paths)
    if n < min_loaded:
        return (
            False,
            f"Forced skill load: view_file ≤{max_loaded} SKILL.md then "
            f"record_skills_loaded(task_id, paths=[...]) — have {n}, need ≥{min_loaded}. "
            "Shortlist without view_file does not count. Overconfidence is not a waiver.",
        )
    if n > max_loaded:
        return (
            False,
            f"Too many skills_loaded ({n}>{max_loaded}) — brain bloat. Keep ≤{max_loaded}.",
        )
    return True, f"skills_loaded OK ({n})."


def assert_phase_skill_gate(
    state: TaskState,
    target_phase: Phase | str,
) -> tuple[bool, str]:
    phase = Phase(target_phase) if isinstance(target_phase, str) else target_phase
    kind = state.handle.kind

    need_catalog = False
    need_loaded = False
    if kind in (TaskKind.FEATURE, TaskKind.REFACTOR):
        need_catalog = phase in PHASES_NEED_CATALOG
        need_loaded = phase in PHASES_NEED_LOADED
    elif kind == TaskKind.BUGFIX:
        need_catalog = phase in BUGFIX_NEED_CATALOG
        need_loaded = phase in {Phase.VERIFY, Phase.CLAIM_DONE}

    if need_catalog:
        ok, reason = catalog_gate(state)
        if not ok:
            return ok, reason
    if need_loaded:
        ok, reason = loaded_gate(state)
        if not ok:
            return ok, reason
    return True, "Skill look-then-choose gates OK."


def claim_skill_gate(state: TaskState) -> tuple[bool, str]:
    if state.handle.kind == TaskKind.BUGFIX:
        ok, reason = catalog_gate(state)
        if not ok:
            return ok, reason
        return loaded_gate(state, min_loaded=1)
    if state.handle.kind in (TaskKind.FEATURE, TaskKind.REFACTOR):
        ok, reason = catalog_gate(state)
        if not ok:
            return ok, reason
        return loaded_gate(state, min_loaded=1)
    return True, "Skill gate N/A."


def build_catalog_evidence_payload(
    query: str,
    *,
    shortlist_paths: Optional[Sequence[str]] = None,
    returned: int = 0,
) -> Dict[str, Any]:
    return {
        "source": "skill_catalog",
        "kind": "skill_scan",
        "query": query or "",
        "shortlist_paths": list(shortlist_paths or []),
        "returned": returned,
        "anti_excuse": "training_memory_or_confidence_does_not_waive",
    }


def build_loaded_payload(paths: Sequence[str]) -> Dict[str, Any]:
    cleaned = [str(p).strip() for p in paths if str(p).strip()]
    return {
        "source": "skills_loaded",
        "kind": "skills_loaded",
        "paths": cleaned,
        "count": len(cleaned),
    }
