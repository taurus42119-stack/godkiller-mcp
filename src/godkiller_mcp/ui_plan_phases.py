"""UI-only plan phase requirements — bake playtest into PLAN, not only claim.

When a plan touches UI / web / game / visual surfaces, plan_validate must
require dedicated phases: long playtest -> capture -> visual inspect -> recheck.
API/backend-only plans skip this gate.

Optional locale aliases: set GODKILLER_LOCALE=th to also match Thai intent keywords.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

_UI_PHASE_INTENTS_EN: Dict[str, Tuple[str, ...]] = {
    "playtest": (
        "playtest",
        "play for real",
        "long play",
        "soak",
        "manual play",
        "serious play",
        "hands-on qa",
    ),
    "capture": (
        "capture",
        "screenshot",
        "visual_step",
        "screen shot",
        "ui journey",
        "gk_evidence.visual_step",
    ),
    "inspect": (
        "inspect",
        "visual_critic",
        "read image",
        "visionbridge",
        "vision bridge",
        "analyze screenshot",
        "read video",
        "pixel qa",
        "visual inspect",
    ),
    "recheck": (
        "recheck",
        "re-check",
        "second pass",
        "visual recheck",
        "re-verify visual",
        "final visual pass",
    ),
}

_UI_PHASE_INTENTS_TH: Dict[str, Tuple[str, ...]] = {
    "playtest": ("ใช้งานจริง", "เล่นจริง", "เล่นยาว", "ทดสอบใช้งาน"),
    "capture": ("แคป", "ถ่ายภาพ"),
    "inspect": ("อ่านรูป", "อ่านวิดีโอ"),
    "recheck": ("เช็คอีกรอบ", "ตรวจอีกรอบ"),
}


def _locale_th() -> bool:
    return os.environ.get("GODKILLER_LOCALE", "").strip().lower() in ("th", "thai", "th-th")


def _ui_phase_intents() -> Dict[str, Tuple[str, ...]]:
    out: Dict[str, Tuple[str, ...]] = {k: tuple(v) for k, v in _UI_PHASE_INTENTS_EN.items()}
    if _locale_th():
        for k, extra in _UI_PHASE_INTENTS_TH.items():
            out[k] = out.get(k, ()) + tuple(extra)
    return out


# Snapshot for importers; runtime helpers call _ui_phase_intents() for live locale.
UI_PHASE_INTENTS = _UI_PHASE_INTENTS_EN

UI_SIGNAL_RE = re.compile(
    r"\b("
    r"ui|ux|gui|hud|frontend|front-end|web\s*app|website|dashboard|landing\s*page|"
    r"react|vue|svelte|next\.?js|three\.?js|babylon|unity|unreal|godot|"
    r"game|3d\s*game|fps|canvas|css|html|screenshot|browser|chrome-devtools|"
    r"visual|pixel|menu\s*screen|title\s*screen|playable|"
    r"saas\s*ui|accounting\s*ui|invoice\s*ui"
    r")\b",
    re.I,
)

UI_SIGNAL_RE_TH = re.compile(r"หน้าจอ|เว็บแอป|เกม|อินเทอร์เฟซ|ยูไอ", re.I)

BACKEND_ONLY_RE = re.compile(
    r"\b(api[\s_-]?only|backend[\s_-]?only|cli[\s_-]?only|library[\s_-]?only|"
    r"headless|no[\s_-]?ui|surface\s*=\s*api)\b",
    re.I,
)

CANONICAL_UI_PHASES: Tuple[Dict[str, str], ...] = (
    {
        "id": "playtest",
        "title": "Long real playtest / soak",
        "dod": "Run the live UI/game for a serious stretch; note bugs; no claim from unit tests alone.",
    },
    {
        "id": "capture",
        "title": "Capture stepwise screenshots (~8-10 visual_step)",
        "dod": "While running: gk_evidence.visual_step for each step_id; proof in chat + disk.",
    },
    {
        "id": "inspect",
        "title": "Inspect captures (visual_critic / VisionBridge)",
        "dod": "Each shot GREEN with expected_elements; read images (video optional later).",
    },
    {
        "id": "recheck",
        "title": "Visual recheck pass",
        "dod": "Second play + spot-check captures; fix regressions; gk_evidence.visual_sequence ok.",
    },
)


def _blob_from_plan(
    *,
    goal: str = "",
    steps: Optional[Dict[str, str]] = None,
    phases: Optional[Sequence[Any]] = None,
    extra_text: str = "",
) -> str:
    parts: List[str] = [goal or "", extra_text or ""]
    for k, v in (steps or {}).items():
        parts.append(f"{k} {v}")
    for p in phases or []:
        if isinstance(p, dict):
            parts.append(str(p.get("name") or p.get("title") or ""))
            parts.append(str(p.get("description") or p.get("dod") or ""))
        else:
            parts.append(str(getattr(p, "name", "") or p))
            parts.append(str(getattr(p, "description", "") or ""))
    return "\n".join(parts)


def detect_ui_plan_work(
    *,
    goal: str = "",
    steps: Optional[Dict[str, str]] = None,
    phases: Optional[Sequence[Any]] = None,
    metadata: Optional[dict] = None,
    ui_work: Optional[bool] = None,
    extra_text: str = "",
) -> bool:
    """True when this plan must include UI playtest phases."""
    meta = metadata or {}
    if ui_work is False or meta.get("require_visual") is False:
        return False
    if ui_work is True or meta.get("require_visual") is True or meta.get("ui_work") is True:
        return True
    surface = str(meta.get("surface") or "").lower().strip()
    if surface in {"api", "backend", "cli", "library", "headless"}:
        return False
    blob = _blob_from_plan(goal=goal, steps=steps, phases=phases, extra_text=extra_text)
    if BACKEND_ONLY_RE.search(blob) and not UI_SIGNAL_RE.search(blob):
        if not (_locale_th() and UI_SIGNAL_RE_TH.search(blob)):
            return False
    if UI_SIGNAL_RE.search(blob):
        return True
    if _locale_th() and UI_SIGNAL_RE_TH.search(blob):
        return True
    return False


def _phase_corpus(
    phases: Optional[Sequence[Any]],
    steps: Optional[Dict[str, str]] = None,
    extra_text: str = "",
) -> str:
    """Corpus for UI intents — Phase N headings only (not buried 8_test_plan prose)."""
    from godkiller_mcp.phase_heading_gate import extract_phase_headings

    parts: List[str] = []
    for h in extract_phase_headings(extra_text or "", phases):
        parts.append(str(h.get("raw") or ""))
        parts.append(str(h.get("title") or ""))
    for p in phases or []:
        if isinstance(p, dict):
            name = str(p.get("name") or p.get("title") or "")
            parts.append(name)
            parts.append(str(p.get("description") or p.get("dod") or ""))
        else:
            parts.append(str(getattr(p, "name", "") or p))
            parts.append(str(getattr(p, "description", "") or ""))
    del steps  # intents must live on Phase headings for front-door clarity
    return "\n".join(parts).lower()


def missing_ui_phase_intents(
    *,
    phases: Optional[Sequence[Any]] = None,
    steps: Optional[Dict[str, str]] = None,
    extra_text: str = "",
) -> List[str]:
    corpus = _phase_corpus(phases, steps, extra_text=extra_text)
    missing: List[str] = []
    for intent, needles in _ui_phase_intents().items():
        if not any(n.lower() in corpus for n in needles):
            missing.append(intent)
    return missing


def evaluate_ui_plan_phases(
    *,
    goal: str = "",
    steps: Optional[Dict[str, str]] = None,
    phases: Optional[Sequence[Any]] = None,
    metadata: Optional[dict] = None,
    ui_work: Optional[bool] = None,
    extra_text: str = "",
) -> Dict[str, Any]:
    needed = detect_ui_plan_work(
        goal=goal,
        steps=steps,
        phases=phases,
        metadata=metadata,
        ui_work=ui_work,
        extra_text=extra_text,
    )
    if not needed:
        return {
            "ui_work": False,
            "ok": True,
            "missing_intents": [],
            "required_phases": [],
            "reason": "UI playtest phases not required (non-UI / API surface).",
        }
    missing = missing_ui_phase_intents(
        phases=phases, steps=steps, extra_text=extra_text
    )
    ok = not missing
    return {
        "ui_work": True,
        "ok": ok,
        "missing_intents": missing,
        "required_phases": [dict(p) for p in CANONICAL_UI_PHASES],
        "reason": (
            "UI plan phases OK (playtest -> capture -> inspect -> recheck on ### Phase N)."
            if ok
            else (
                "UI plan incomplete: must name dedicated ### Phase N titles for "
                + ", ".join(missing)
                + " (long real play -> stepwise capture -> inspect shots -> recheck). "
                "Keywords only inside 8_test_plan without ### Phase N do NOT count."
            )
        ),
    }


def format_canonical_ui_phases_markdown(start_n: int = 1) -> str:
    lines: List[str] = []
    n = start_n
    for p in CANONICAL_UI_PHASES:
        lines.append(f"### Phase {n} — {p['title']}")
        lines.append(f"- [ ] {p['dod']}")
        lines.append(f"- DoD: {p['dod']}")
        n += 1
    return "\n".join(lines)
