"""ROI gates — smarter defaults without theatre.

1. PROFILE=ship claim needs WRITE_GUARD_PROVEN (host must attest live PreToolUse).
   This does **not** close native Write by itself — it refuses ship *claim_done*
   until the operator marks the hook proven.
2. Bugfix edit route: search evidence + blast_radius before check_edit_safe.
3. Fail recipes from lessons inject into plan templates.
4. Exhaustive dump blocked until symbol intel (jcodemunch / map / search digest).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from godkiller_mcp.schema import EvidenceType, TaskKind, TaskState
from godkiller_mcp.ship_mode import profile, relax_enabled


def write_guard_is_proven() -> bool:
    return os.environ.get("GODKILLER_WRITE_GUARD_PROVEN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def require_write_guard_proven_for_ship() -> bool:
    """True when ship PROFILE demands proven write-guard before claim."""
    if profile() != "ship":
        return False
    if relax_enabled():
        return False
    raw = os.environ.get("GODKILLER_REQUIRE_WRITE_GUARD_PROVEN", "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def claim_write_guard_gate() -> Tuple[bool, str]:
    """Ship claim armor: native Write stays host-side; claim blocks until PROVEN."""
    if not require_write_guard_proven_for_ship():
        return True, "write_guard ship-proven gate off (not PROFILE=ship)"
    if write_guard_is_proven():
        return True, "WRITE_GUARD_PROVEN set"
    return (
        False,
        "PROFILE=ship: set GODKILLER_WRITE_GUARD_PROVEN=1 only after live PreToolUse "
        "deny/allow via godkiller-write-guard — native Write still bypasses MCP until then. "
        "See docs/WRITE_GUARD_HOOKS.md / docs/HOST_VS_MCP.md",
    )


def bugfix_edit_route_gate(state: TaskState) -> Tuple[bool, str]:
    """Force search → blast before edit on bugfix (auto-route, not theatre)."""
    if state.handle.kind != TaskKind.BUGFIX:
        return True, "not bugfix"
    if relax_enabled():
        return True, "bugfix route skipped (DEV_RELAX)"

    from godkiller_mcp.search_gates import search_gate

    ok_s, reason_s, _qs = search_gate(state)
    if not ok_s:
        return (
            False,
            "bugfix auto-route: record search evidence first (≥3 queries), then "
            f"blast_radius, then edit_safe. ({reason_s})",
        )

    if EvidenceType.BLAST_RADIUS not in state.evidence_types():
        return (
            False,
            "bugfix auto-route: call blast_radius (localize) before check_edit_safe",
        )
    return True, "bugfix route OK (search + blast)"


_SYMBOL_SOURCES = frozenset(
    {
        "jcodemunch",
        "codebase_memory",
        "repo_map",
        "hyper_search",
        "symbol_intel",
        "ast_grep",
        "fast_find",
    }
)


def _digest_ok(raw: Any) -> bool:
    s = str(raw or "").strip()
    return len(s) >= 24


def symbol_intel_satisfied(
    arguments: Optional[Dict[str, Any]] = None,
    state: Optional[TaskState] = None,
) -> Tuple[bool, str]:
    """Allow exhaustive only after targeted symbol context exists."""
    if relax_enabled():
        return True, "exhaustive gate skipped (DEV_RELAX)"
    if os.environ.get("GODKILLER_ALLOW_EXHAUSTIVE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True, "GODKILLER_ALLOW_EXHAUSTIVE=1"

    args = arguments or {}
    for key in (
        "symbol_digest",
        "jcodemunch_digest",
        "symbol_context",
        "ranked_context",
    ):
        if _digest_ok(args.get(key)):
            return True, f"symbol intel via arg:{key}"

    if args.get("force_exhaustive") and relax_enabled():
        return True, "force_exhaustive under relax"

    if state is not None:
        meta = state.handle.metadata or {}
        si = meta.get("symbol_intel") or {}
        if isinstance(si, dict):
            src = str(si.get("source") or "").lower()
            if src in _SYMBOL_SOURCES and (
                _digest_ok(si.get("digest")) or bool(si.get("ok"))
            ):
                return True, f"task metadata symbol_intel ({src})"
        for ev in reversed(list(getattr(state, "evidences", []) or [])):
            payload = ev.payload or {}
            src = str(payload.get("source") or "").lower()
            if src in _SYMBOL_SOURCES and (
                _digest_ok(payload.get("digest"))
                or _digest_ok(payload.get("summary"))
                or bool(payload.get("ok"))
            ):
                return True, f"evidence source={src}"

    return (
        False,
        "exhaustive_read blocked: get symbol intel first "
        "(prefer jcodemunch / codebase-memory ranked symbols, or gk_code.map / "
        "gk_code.search), pass symbol_digest=… (≥24 chars), or stamp task via "
        "repo_map/hyper_search with task_id. Dump-all without map burns tokens.",
    )


def stamp_symbol_intel(
    store: Any,
    task_id: Optional[str],
    *,
    source: str,
    digest: str,
) -> None:
    if not task_id or not digest:
        return
    try:
        store.update_metadata(
            task_id,
            {
                "symbol_intel": {
                    "ok": True,
                    "source": source,
                    "digest": str(digest)[:4000],
                }
            },
        )
    except Exception:
        pass


def format_fail_recipes(lessons: List[Dict[str, Any]], *, limit: int = 4) -> str:
    lines: List[str] = []
    for item in lessons[:limit]:
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        tag = ",".join(item.get("tags") or []) or "fail"
        lines.append(f"- [{tag}] {content[:400]}")
    if not lines:
        return ""
    return (
        "Fail recipes from prior verified failures (do not repeat):\n"
        + "\n".join(lines)
    )


def inject_fail_recipes(
    plan: Dict[str, Any],
    recipes_text: str,
) -> Dict[str, Any]:
    """Merge fail recipes into plan template steps without inventing confidence."""
    if not recipes_text.strip():
        plan.setdefault("fail_recipes", [])
        plan["fail_recipes_note"] = "no fail lessons on disk yet"
        return plan
    steps = dict(plan.get("steps") or {})
    cur = (steps.get("4_current_state") or "").strip()
    block = recipes_text.strip()
    if block not in cur:
        steps["4_current_state"] = (cur + "\n\n" + block).strip() if cur else block
    cons = (steps.get("2_constraints") or "").strip()
    tip = "Avoid repeating fail recipes listed in 4_current_state."
    if tip not in cons:
        steps["2_constraints"] = (cons + "\n" + tip).strip() if cons else tip
    plan["steps"] = steps
    plan["fail_recipes_injected"] = True
    plan["fail_recipes_note"] = (
        "Injected from lessons DB (task_passed=0, verified) — not praise, not confidence%"
    )
    return plan
