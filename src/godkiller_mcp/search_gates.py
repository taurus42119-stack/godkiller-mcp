"""Forced epistemics - search evidence before plan/build/claim.

SUPREME LAW: applies to every user task (game, software, hardware, web,
design, data, other). Local skills never waive search. Only the shape of
evidence changes by surface - never the ambition bar.
Visual gates are separate (see quality_gates.needs_visual_loop).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from godkiller_mcp.schema import Phase, TaskKind, TaskState


# Minimum recorded search queries by kind
MIN_QUERIES = {
    TaskKind.FEATURE: 5,
    TaskKind.BUGFIX: 3,
    TaskKind.REFACTOR: 3,
}

# Entering these phases without search is blocked (feature/refactor)
PHASES_REQUIRING_SEARCH = {
    Phase.HYPOTHESIZE,
    Phase.LOCALIZE,
    Phase.FIX,
    Phase.VERIFY,
    Phase.CLAIM_DONE,
}

# Bugfix: must search before first FIX attempt
BUGFIX_PHASES_REQUIRING_SEARCH = {
    Phase.FIX,
    Phase.VERIFY,
    Phase.CLAIM_DONE,
}

BACKEND_SURFACES = frozenset({"api", "backend", "library", "cli", "batch", "data"})


def min_queries_for_kind(kind: TaskKind | str) -> int:
    k = TaskKind(kind) if isinstance(kind, str) else kind
    return MIN_QUERIES.get(k, 5)


def extract_queries_from_payload(payload: Optional[dict]) -> List[str]:
    if not payload:
        return []
    out: List[str] = []
    raw = payload.get("queries") or payload.get("search_queries") or []
    if isinstance(raw, str):
        raw = [raw]
    for q in raw:
        s = str(q).strip()
        # B7: reject ceremonial one-letter / tiny padding strings
        if len(s) >= 8 and not s.isdigit():
            out.append(s)
    return out


def is_web_search_evidence(payload: Optional[dict]) -> bool:
    if not payload:
        return False
    src = str(payload.get("source") or "").lower()
    kind = str(payload.get("kind") or "").lower()
    if src in ("web_search", "search_web", "social_osint", "competitor_scan"):
        return True
    if kind in ("web_search", "search_web", "social_osint"):
        return True
    return bool(extract_queries_from_payload(payload))


def collect_search_queries(state: TaskState) -> List[str]:
    """Union of queries recorded on the task evidence graph."""
    seen: List[str] = []
    for ev in state.evidence:
        payload = ev.payload or {}
        if not is_web_search_evidence(payload):
            continue
        for q in extract_queries_from_payload(payload):
            if q not in seen:
                seen.append(q)
        # competitor_scan without explicit queries still counts as 1 epistemic act
        # only if named competitors present — prefer explicit queries
    meta_q = (state.handle.metadata or {}).get("search_queries") or []
    if isinstance(meta_q, str):
        meta_q = [meta_q]
    for q in meta_q:
        s = str(q).strip()
        if s and s not in seen:
            seen.append(s)
    return seen


def search_gate(
    state: TaskState,
    *,
    min_queries: Optional[int] = None,
) -> tuple[bool, str, List[str]]:
    need = min_queries if min_queries is not None else min_queries_for_kind(state.handle.kind)
    queries = collect_search_queries(state)
    n = len(queries)
    if n < need:
        return (
            False,
            (
                f"Forced search gate: need ≥{need} recorded search queries for "
                f"{state.handle.kind.value}; have {n}. "
                "Call search_web, then submit_evidence with "
                '{ "source":"web_search", "queries":[...] } '
                "or marathon_save_progress(search_queries=...). "
                "Local skills do NOT waive this."
            ),
            queries,
        )
    return True, f"Search gate OK ({n} ≥ {need}).", queries


def phase_requires_search(kind: TaskKind, phase: Phase) -> bool:
    if kind == TaskKind.BUGFIX:
        return phase in BUGFIX_PHASES_REQUIRING_SEARCH
    if kind in (TaskKind.FEATURE, TaskKind.REFACTOR):
        return phase in PHASES_REQUIRING_SEARCH
    return False


def assert_phase_search_gate(
    state: TaskState,
    target_phase: Phase | str,
) -> tuple[bool, str]:
    phase = Phase(target_phase) if isinstance(target_phase, str) else target_phase
    if not phase_requires_search(state.handle.kind, phase):
        return True, "Search not required for this phase."
    ok, reason, _ = search_gate(state)
    return ok, reason


def claim_search_gate(state: TaskState) -> tuple[bool, str]:
    ok, reason, _ = search_gate(state)
    return ok, reason


def write_spec_search_gate(
    queries: Sequence[str],
    *,
    kind: TaskKind | str = TaskKind.FEATURE,
    min_queries: Optional[int] = None,
    marathon_queries: Optional[Sequence[str]] = None,
) -> tuple[bool, str, List[str]]:
    merged: List[str] = []
    for src in (queries, marathon_queries or []):
        for q in src:
            s = str(q).strip()
            if s and s not in merged:
                merged.append(s)
    need = min_queries if min_queries is not None else min_queries_for_kind(kind)
    if len(merged) < need:
        return (
            False,
            (
                f"write_spec blocked: need ≥{need} search_queries "
                f"(got {len(merged)}). Run search_web first; skills never replace search."
            ),
            merged,
        )
    return True, f"write_spec search OK ({len(merged)} queries).", merged


def needs_visual_loop(state: TaskState, *, require_for_feature: bool = True) -> bool:
    """UI/SaaS/games need visual gates; pure API/backend can opt out via metadata."""
    meta = state.handle.metadata or {}
    if meta.get("require_visual") is False:
        return False
    if meta.get("require_visual") is True or meta.get("require_quality_loop"):
        return True
    surface = str(meta.get("surface") or "").lower().strip()
    if surface in BACKEND_SURFACES:
        return False
    if require_for_feature and state.handle.kind == TaskKind.FEATURE:
        return True  # default: accounting/SaaS/game products have UI
    return False


def normalize_web_search_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure submit_evidence payloads are countable by search_gate."""
    out = dict(payload)
    queries = extract_queries_from_payload(out)
    if queries and not out.get("source"):
        out["source"] = "web_search"
    if queries and not out.get("kind"):
        out["kind"] = "web_search"
    if queries:
        out["queries"] = queries
    return out
