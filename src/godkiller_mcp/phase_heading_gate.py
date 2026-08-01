"""Front-facing plan headings — user must see ### Phase N, not subsystem titles.

MCP used to pass plan_validate on 9-step JSON + keyword intents while the
Markdown artifact used bare technical H3s (module/system names). That hides
the phase ladder from humans. Domain-agnostic: games, SaaS, hardware, APIs.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# Canonical visible form: ### Phase 1 — Title  (also ## / ####, Thai เฟส, checklist)
PHASE_HEADING_RE = re.compile(
    r"^(#{2,4})\s*Phase\s+(\d+)\s*(?:[—\-:–]\s*|\s+)?(.*)$",
    re.I | re.M,
)
PHASE_TH_RE = re.compile(
    r"^(#{2,4})\s*เฟส\s*(\d+)\s*(?:[—\-:–]\s*|\s+)?(.*)$",
    re.M,
)
PHASE_LIST_RE = re.compile(
    r"^[-*]\s*(?:\[[ xX]\]\s*)?Phase\s+(\d+)\s*(?:[—\-:–]\s*|\s+)?(.*)$",
    re.I | re.M,
)
# Any markdown ### / ## heading (for anti-pattern detection)
ANY_HEADING_RE = re.compile(r"^(#{2,4})\s+(.+)$", re.M)

# Titles that look like feature subsystems — any domain (not games-only)
TECH_HEADING_HINT_RE = re.compile(
    r"\b(system|module|subsystem|service|pipeline|layer|engine|"
    r"weapons?|hands?|world|inventory|hud|combat|mesh|shader|"
    r"networking|audio|physics|animation|rendering|"
    r"auth|billing|invoice|ledger|dashboard|checkout|catalog|"
    r"schema|migration|api\s*gateway|firmware|schematic)\b",
    re.I,
)


def _phase_name_ok(name: str) -> Optional[Dict[str, Any]]:
    s = (name or "").strip()
    if not s:
        return None
    m = PHASE_HEADING_RE.match(s) or PHASE_HEADING_RE.search(s)
    if m:
        return {
            "n": int(m.group(2)),
            "title": (m.group(3) or "").strip(),
            "raw": s,
            "level": len(m.group(1)),
        }
    m = PHASE_TH_RE.match(s) or PHASE_TH_RE.search(s)
    if m:
        return {
            "n": int(m.group(2)),
            "title": (m.group(3) or "").strip(),
            "raw": s,
            "level": len(m.group(1)),
        }
    m = PHASE_LIST_RE.match(s) or PHASE_LIST_RE.search(s)
    if m:
        return {"n": int(m.group(1)), "title": (m.group(2) or "").strip(), "raw": s}
    loose = re.match(r"^Phase\s+(\d+)\b\s*(?:[—\-:–]\s*)?(.*)$", s, re.I)
    if loose:
        return {"n": int(loose.group(1)), "title": (loose.group(2) or "").strip(), "raw": s}
    loose_th = re.match(r"^เฟส\s*(\d+)\b\s*(?:[—\-:–]\s*)?(.*)$", s)
    if loose_th:
        return {"n": int(loose_th.group(1)), "title": (loose_th.group(2) or "").strip(), "raw": s}
    return None


def extract_phase_headings(
    text: str = "",
    phases: Optional[Sequence[Any]] = None,
) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    seen: set[int] = set()

    def _add(info: Optional[Dict[str, Any]]) -> None:
        if not info:
            return
        n = int(info["n"])
        if n in seen:
            return
        seen.add(n)
        found.append(info)

    blob = text or ""
    for rx in (PHASE_HEADING_RE, PHASE_TH_RE, PHASE_LIST_RE):
        for m in rx.finditer(blob):
            if rx is PHASE_LIST_RE:
                _add({"n": int(m.group(1)), "title": (m.group(2) or "").strip(), "raw": m.group(0)})
            else:
                _add(
                    {
                        "n": int(m.group(2)),
                        "title": (m.group(3) or "").strip(),
                        "raw": m.group(0).strip(),
                        "level": len(m.group(1)),
                    }
                )

    for p in phases or []:
        if isinstance(p, dict):
            name = str(p.get("name") or p.get("title") or "")
            desc = str(p.get("description") or p.get("dod") or "")
            info = _phase_name_ok(name)
            if info:
                if desc and not info.get("title"):
                    info["title"] = desc
                _add(info)
            else:
                # Allow description-only if name is technical but description starts with Phase N
                info2 = _phase_name_ok(desc)
                _add(info2)
        else:
            _add(_phase_name_ok(str(getattr(p, "name", "") or p)))

    found.sort(key=lambda x: x["n"])
    return found


def extract_non_phase_headings(text: str) -> List[str]:
    """### headings that are NOT Phase N — front-door smell."""
    out: List[str] = []
    for m in ANY_HEADING_RE.finditer(text or ""):
        body = (m.group(2) or "").strip()
        if re.match(r"^(Phase|เฟส)\s*\d+\b", body, re.I):
            continue
        # Ignore top-level plan schema sections (1. Core Objective, etc.)
        if re.match(
            r"^("
            r"\d+[\.\)]\s|"
            r"[🎯🔬📦💣🕸️🛡️🎨📂🧪]|"
            r"core objective|research log|dependency|blast radius|"
            r"golden architecture|enterprise|reference|phased execution|"
            r"dod|test strategy|goal|constraints|stakeholders"
            r")",
            body,
            re.I,
        ):
            continue
        out.append(body)
    return out


def evaluate_phase_heading_gate(
    *,
    text: str = "",
    phases: Optional[Sequence[Any]] = None,
    min_phases: int = 2,
    metadata: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Fail-closed: humans must see ### Phase 1, ### Phase 2, …

    Technical headings like ### Auth Module or ### Billing Service do not count.
    Works for games, SaaS, hardware, APIs — same rule.
    """
    meta = metadata or {}
    if meta.get("require_phase_headings") is False:
        return {
            "ok": True,
            "skipped": True,
            "phase_headings": [],
            "reason": "phase heading gate skipped via metadata.",
        }
    try:
        need = int(meta.get("min_plan_phases") or min_phases)
    except (TypeError, ValueError):
        need = min_phases
    need = max(1, need)

    headings = extract_phase_headings(text, phases)
    tech = extract_non_phase_headings(text)
    tech_smelly = [t for t in tech if TECH_HEADING_HINT_RE.search(t)]

    ok = len(headings) >= need
    reasons: List[str] = []
    if not ok:
        reasons.append(
            f"Front-facing plan needs ≥{need} numbered headings like "
            f"`### Phase 1 — …`, `### Phase 2 — …` (have {len(headings)}). "
            "Any domain: do NOT use bare subsystem H3s as the phase ladder "
            "(e.g. `### Auth Module`, `### Invoice Ledger`, `### World System`) — "
            "rename to `### Phase N — <same title>`."
        )
    if tech_smelly and len(headings) < need:
        reasons.append(
            "Detected technical subsection titles without Phase N prefix: "
            + ", ".join(f"`### {t}`" for t in tech_smelly[:5])
        )

    return {
        "ok": ok,
        "skipped": False,
        "min_phases": need,
        "phase_count": len(headings),
        "phase_headings": headings,
        "technical_headings_without_phase": tech_smelly,
        "reason": (
            "Phase headings OK (### Phase N visible to user)."
            if ok
            else " | ".join(reasons)
        ),
        "example": (
            "### Phase 1 — Auth Module\n"
            "### Phase 2 — Invoice Ledger\n"
            "### Phase 3 — Verify + soak"
        ),
    }
