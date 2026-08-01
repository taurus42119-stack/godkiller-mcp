"""Multi-step visual QA — run → capture → inspect → claim.

One dump screenshot is not enough. Surfaces that need visual proof must
accumulate a sequence of on-disk shots, each inspected by visual_critic
(VisionBridge) before claim_done.

Anti-cheat: repeating one host/IDE chrome OCR token on every shot does not
satisfy the sequence — expected_elements must be surface labels that vary by step.
Domain-agnostic: works for UI, web, games, docs, tools — labels come from the
artifact under test, never from fixed product vocabulary in this module's UX copy.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from godkiller_mcp.schema import EvidenceType, TaskState

# Default 10-step story (agent must capture while the surface is running).
# Structural ids only — domain labels live in per-shot expected_elements.
DEFAULT_STEP_IDS: tuple[str, ...] = (
    "01_boot",
    "02_title_or_menu",
    "03_enter_play",
    "04_gameplay_idle",
    "05_primary_action",
    "06_hud_readable",
    "07_secondary_state",
    "08_after_interaction",
    "09_edge_or_stable",
    "10_final_frame",
)

# Host/IDE chrome tokens — never valid as the sole expected_elements set.
# Kept as an internal set only; user-facing errors must not enumerate brands.
WATERMARK_ONLY_BLOCKLIST: frozenset[str] = frozenset(
    {
        "claude",
        "cursor",
        "antigravity",
        "chatgpt",
        "gemini",
        "copilot",
        "godkiller",
        "openai",
        "anthropic",
    }
)


def min_visual_shots(meta: Optional[dict] = None) -> int:
    meta = meta or {}
    if meta.get("visual_min_shots") is not None:
        try:
            return max(1, int(meta["visual_min_shots"]))
        except (TypeError, ValueError):
            pass
    env = os.environ.get("GODKILLER_VISUAL_MIN_SHOTS", "").strip()
    if env.isdigit():
        return max(1, int(env))
    return 10


def required_step_ids(meta: Optional[dict] = None) -> List[str]:
    meta = meta or {}
    custom = meta.get("visual_step_ids")
    if isinstance(custom, (list, tuple)) and custom:
        return [str(x).strip() for x in custom if str(x).strip()]
    n = min_visual_shots(meta)
    if n <= len(DEFAULT_STEP_IDS):
        return list(DEFAULT_STEP_IDS[:n])
    return list(DEFAULT_STEP_IDS) + [
        f"{i:02d}_extra" for i in range(len(DEFAULT_STEP_IDS) + 1, n + 1)
    ]


def min_distinct_element_sets(need: int, meta: Optional[dict] = None) -> int:
    """How many different expected_elements signatures are required across GREEN shots."""
    meta = meta or {}
    if meta.get("visual_min_element_sets") is not None:
        try:
            return max(1, int(meta["visual_min_element_sets"]))
        except (TypeError, ValueError):
            pass
    # e.g. need=10 → 5; need=3 → 3
    return max(1, min(need, max(3, (need + 1) // 2)))


def normalize_expected_elements(elems: Optional[Sequence[Any]]) -> Tuple[str, ...]:
    out: List[str] = []
    for x in elems or []:
        s = str(x).strip()
        if s:
            out.append(s)
    return tuple(out)


def is_watermark_only_elements(elems: Sequence[str]) -> bool:
    cleaned = [str(x).strip().lower() for x in elems if str(x).strip()]
    if not cleaned:
        return False
    return all(e in WATERMARK_ONLY_BLOCKLIST for e in cleaned)


def watermark_elements_rejected(elems: Sequence[str]) -> Optional[str]:
    if is_watermark_only_elements(elems):
        return (
            "expected_elements cannot be only host/IDE chrome labels. "
            "Use visible text from the artifact under test for THIS step_id "
            "(labels must come from the surface, not the chat/IDE chrome)."
        )
    return None


def _norm_path(p: str) -> str:
    raw = str(p or "").strip()
    if not raw:
        return ""
    try:
        from pathlib import Path

        rp = Path(raw)
        if rp.exists():
            raw = str(rp.resolve())
    except OSError:
        pass
    return raw.replace("\\", "/").lower().strip()


def collect_screenshot_records(state: TaskState) -> List[Dict[str, Any]]:
    """Unique screenshot paths with optional step_id from evidence payloads."""
    by_path: Dict[str, Dict[str, Any]] = {}
    for ev in state.evidence:
        payload = ev.payload or {}
        src = str(payload.get("source") or "").lower()
        path = ""
        if ev.type == EvidenceType.SCREENSHOT:
            path = str(payload.get("path") or ev.uri or "")
            if payload.get("exists") is False:
                continue
        elif src == "capture_shot":
            path = str(payload.get("path") or payload.get("screenshot_path") or ev.uri or "")
        elif src == "visual_step":
            path = str(payload.get("path") or "")
        if not path:
            continue
        key = _norm_path(path)
        step = str(payload.get("step_id") or payload.get("step") or "").strip()
        rec = by_path.get(key) or {"path": path, "step_id": step or None, "uris": []}
        if step:
            rec["step_id"] = step
        rec["uris"].append(ev.uri or path)
        by_path[key] = rec

    for ev in state.evidence:
        if ev.type != EvidenceType.UI_JOURNEY:
            continue
        payload = ev.payload or {}
        for uri in payload.get("screenshot_uris") or []:
            if not uri:
                continue
            key = _norm_path(str(uri))
            if key not in by_path:
                by_path[key] = {"path": str(uri), "step_id": None, "uris": [str(uri)]}
    return list(by_path.values())


def collect_green_critic_records(state: TaskState) -> List[Dict[str, Any]]:
    """GREEN VisionBridge critics that are not watermark-only cheats."""
    out: List[Dict[str, Any]] = []
    for ev in state.evidence:
        payload = ev.payload or {}
        if str(payload.get("source") or "") != "visual_critic":
            continue
        if str(payload.get("verdict") or "").upper() != "GREEN":
            continue
        vision = payload.get("vision")
        if not isinstance(vision, dict) or not vision.get("passed"):
            continue
        path = str(vision.get("path") or payload.get("screenshot_path") or "")
        if not path:
            continue
        elems = normalize_expected_elements(
            vision.get("expected_elements") or payload.get("expected_elements")
        )
        if is_watermark_only_elements(elems):
            continue
        out.append(
            {
                "path": path,
                "norm_path": _norm_path(path),
                "elements": elems,
                "element_key": frozenset(e.lower() for e in elems),
                "step_id": str(payload.get("step_id") or "").strip() or None,
            }
        )
    return out


def collect_green_critic_paths(state: TaskState) -> Set[str]:
    return {r["norm_path"] for r in collect_green_critic_records(state)}


def evaluate_visual_sequence(state: TaskState) -> Dict[str, Any]:
    """Fail-closed sequence gate for claim_done / ui_proof."""
    meta = state.handle.metadata or {}
    need = min_visual_shots(meta)
    steps_needed = required_step_ids(meta)
    need_sets = min_distinct_element_sets(need, meta)
    shots = collect_screenshot_records(state)
    green_recs = collect_green_critic_records(state)
    greened = {r["norm_path"] for r in green_recs}
    shot_paths = {_norm_path(s["path"]) for s in shots if s.get("path")}
    greened_shots = shot_paths & greened
    # Prefer latest green record per path for diversity
    by_path: Dict[str, Dict[str, Any]] = {}
    for r in green_recs:
        if r["norm_path"] in greened_shots:
            by_path[r["norm_path"]] = r
    element_keys = {r["element_key"] for r in by_path.values() if r.get("element_key")}
    n_distinct = len(element_keys)
    diversity_ok = n_distinct >= need_sets

    step_ids_present = {s["step_id"] for s in shots if s.get("step_id")}
    missing_steps = [s for s in steps_needed if s not in step_ids_present]

    journeys = [e for e in state.evidence if e.type == EvidenceType.UI_JOURNEY]
    journey_ok = any(
        (e.payload or {}).get("passed")
        and len((e.payload or {}).get("screenshot_uris") or []) >= need
        for e in journeys
    )

    n_shots = len(shot_paths)
    n_green = len(greened_shots)
    require_labels = bool(meta.get("require_visual_step_ids", True))
    labels_ok = (not require_labels) or (len(step_ids_present) >= need) or journey_ok
    ok = n_shots >= need and n_green >= need and labels_ok and diversity_ok

    reasons: List[str] = []
    if n_shots < need:
        reasons.append(f"need ≥{need} distinct on-disk screenshots; have {n_shots}")
    if n_green < need:
        reasons.append(
            f"need ≥{need} GREEN visual_critic (VisionBridge) covering those shots; have {n_green}"
            " (host/IDE chrome-only expected_elements do not count)"
        )
    if require_labels and not labels_ok:
        reasons.append(
            "missing step_id labels: "
            + ", ".join(missing_steps[:5])
            + ("…" if len(missing_steps) > 5 else "")
            + " — capture while running (gk_evidence.visual_step)"
        )
    if not diversity_ok:
        reasons.append(
            f"need ≥{need_sets} distinct expected_elements signatures across GREEN shots; "
            f"have {n_distinct}. Do not reuse one OCR token on every step — "
            "vary surface labels per step_id."
        )
    if not reasons and ok:
        reasons.append("visual sequence OK")

    return {
        "ok": ok,
        "min_shots": need,
        "min_distinct_element_sets": need_sets,
        "distinct_element_sets": n_distinct,
        "shots_count": n_shots,
        "green_critic_count": n_green,
        "step_ids_required": steps_needed,
        "step_ids_present": sorted(step_ids_present),
        "missing_step_ids": missing_steps,
        "shot_paths": sorted(shot_paths),
        "greened_paths": sorted(greened_shots),
        "journey_volume_ok": journey_ok,
        "order": (
            "Run the artifact → capture each step (≈10) with gk_evidence.visual_step "
            "(step_id + step-specific expected_elements from the surface) → "
            "AI visual_critic GREEN per shot → then claim."
        ),
        "reasons": reasons,
        "blocked_reason": (
            None
            if ok
            else "Visual sequence gate: " + "; ".join(reasons)
        ),
    }


def visual_sequence_claim_gate(state: TaskState) -> tuple[bool, str]:
    report = evaluate_visual_sequence(state)
    if report["ok"]:
        return True, "Visual sequence gate OK."
    return False, str(report["blocked_reason"] or "Visual sequence incomplete.")
