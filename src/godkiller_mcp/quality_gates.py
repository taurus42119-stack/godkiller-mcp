"""Quality gates: capture, visual critic, soak, competitor compare, ambition ladder.

SUPREME LAW: same ambition for every user task. Placeholder/"good enough"
claims are RED until evidence says otherwise. Domain only changes proof shape
(screenshot vs API tests vs hardware log) — never the competitor/ladder bar.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from godkiller_mcp.safe_exec import run_command_safely
from godkiller_mcp.schema import EvidenceType, TaskKind, TaskState


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class CriticVerdict(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


# Ambition ladder — expand quality in order, not random side-quests
LADDER_LEVELS = ("L0_core", "L1_presence", "L2_motion", "L3_craft", "L4_dominance")

PLACEHOLDER_PATTERNS = [
    re.compile(r"\bsphere\b.*\b(tree|trunk|cylinder)\b", re.I),
    re.compile(r"\bcylinder\b.*\b(tree|trunk)\b", re.I),
    re.compile(r"\bprogrammer[- ]?art\b", re.I),
    re.compile(r"\bplaceholder\b", re.I),
    re.compile(r"\btemp(orary)?\s+(mesh|asset|ui|model)\b", re.I),
    re.compile(r"\bcandy\s*blob\b", re.I),
    re.compile(r"\bsolid\s*color\s*(plane|ground|floor)\b", re.I),
    re.compile(r"\bdefault\s*(font|button|theme)\b", re.I),
    re.compile(r"\bpurple\s*(gradient|on\s*white)\b", re.I),
    re.compile(r"\blorem\s*ipsum\b", re.I),
    re.compile(r"\btodo\b.*\b(ui|visual|texture|model)\b", re.I),
]


@dataclass
class VisualCriticResult:
    verdict: CriticVerdict
    findings: List[str] = field(default_factory=list)
    checklist: Dict[str, bool] = field(default_factory=dict)
    escalate: bool = False
    summary: str = ""

    def to_payload(self) -> Dict[str, Any]:
        base = {
            "source": "visual_critic",
            "verdict": self.verdict.value,
            "findings": self.findings,
            "checklist": self.checklist,
            "escalate": self.escalate,
            "passed": self.verdict == CriticVerdict.GREEN,
            "summary": self.summary,
            "at": _utcnow(),
        }
        extra = getattr(self, "_extra_payload", None)
        if isinstance(extra, dict) and "vision" in extra:
            base["vision"] = extra["vision"]
        return base


@dataclass
class SoakResult:
    passed: bool
    duration_sec: float
    errors: int
    stuck_pct: float
    notes: str = ""
    command: str = ""
    exit_code: Optional[int] = None

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source": "soak_run",
            "passed": self.passed,
            "duration_sec": self.duration_sec,
            "errors": self.errors,
            "stuck_pct": self.stuck_pct,
            "notes": self.notes,
            "command": self.command,
            "exit_code": self.exit_code,
            "at": _utcnow(),
        }


@dataclass
class CompetitorScanResult:
    queries: List[str]
    competitors: List[Dict[str, str]]  # name, url, notes
    min_required: int = 2

    @property
    def passed(self) -> bool:
        return len(self.competitors) >= self.min_required and len(self.queries) >= 1

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source": "competitor_scan",
            "passed": self.passed,
            "queries": self.queries,
            "competitors": self.competitors,
            "min_required": self.min_required,
            "count": len(self.competitors),
            "at": _utcnow(),
        }


@dataclass
class CompareDeltaResult:
    axes: Dict[str, float]  # axis -> delta (ours - competitor); negative = we lose
    still_losing: bool
    notes: str = ""
    best_competitor: str = ""

    @property
    def passed(self) -> bool:
        return not self.still_losing

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source": "compare_delta",
            "passed": self.passed,
            "still_losing": self.still_losing,
            "axes": self.axes,
            "notes": self.notes,
            "best_competitor": self.best_competitor,
            "at": _utcnow(),
        }


def detect_placeholder_signals(text: str) -> List[str]:
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(text or ""):
            hits.append(pat.pattern)
    return hits


def run_visual_critic(
    *,
    kind: str,
    description: str,
    checklist: Optional[Dict[str, bool]] = None,
    agent_verdict: Optional[str] = None,
    findings: Optional[Sequence[str]] = None,
    screenshot_path: Optional[str] = None,
    expected_elements: Optional[Sequence[str]] = None,
) -> VisualCriticResult:
    """
    Pixel-first critic.

    Text regex / agent checklist can only force RED (or annotate findings).
    They cannot produce GREEN without an on-disk screenshot that VisionBridge passes.
    """
    checklist = dict(checklist or {})
    findings_l = list(findings or [])
    blob = " ".join([description or "", " ".join(findings_l), str(checklist)])
    ph = detect_placeholder_signals(blob)
    for p in ph:
        findings_l.append(f"Placeholder signal detected: {p}")

    required_keys = [
        "first_screen_readable",
        "not_placeholder",
        "materials_or_hierarchy_ok",
        "reference_delta_acceptable",
        "pixels_verified",
    ]

    vision_payload: Optional[Dict[str, Any]] = None

    if not screenshot_path:
        findings_l.append(
            "pixels_required: no screenshot_path — regex/checklist alone cannot GREEN"
        )
        for k in required_keys:
            checklist[k] = False
        result = VisualCriticResult(
            verdict=CriticVerdict.RED,
            findings=findings_l,
            checklist=checklist,
            escalate=True,
            summary="visual_critic RED: pixels_required",
        )
        result._extra_payload = {"vision": None, "pixels_required": True}  # type: ignore[attr-defined]
        return result

    from godkiller_mcp.vision_bridge import VisionBridge

    vr = VisionBridge().analyze_screenshot(
        screenshot_path,
        expected_elements=list(expected_elements) if expected_elements else None,
    )
    vision_payload = {
        "passed": vr.passed,
        "score": vr.score,
        "width": vr.width,
        "height": vr.height,
        "is_blank_placeholder": vr.is_blank_placeholder,
        "description": vr.description,
        "elements_found": vr.elements_found,
        "elements_missing": vr.elements_missing,
        "ocr_engine": vr.ocr_engine,
        "path": str(screenshot_path),
    }
    checklist["pixels_verified"] = bool(vr.passed) and not vr.is_blank_placeholder
    if vr.is_blank_placeholder:
        checklist["not_placeholder"] = False
        findings_l.append(f"VisionBridge blank/placeholder: {vr.description}")
    else:
        checklist["not_placeholder"] = True
    if not vr.passed:
        findings_l.append(f"VisionBridge failed: {vr.description}")
        checklist["first_screen_readable"] = False
        checklist["pixels_verified"] = False
    else:
        checklist["first_screen_readable"] = True

    # Soft axes: agent may claim, but only after pixels_verified
    for soft in ("materials_or_hierarchy_ok", "reference_delta_acceptable"):
        if soft not in checklist:
            checklist[soft] = False
        if checklist["pixels_verified"] and checklist.get(soft) is True:
            pass
        elif not checklist["pixels_verified"]:
            checklist[soft] = False

    if ph:
        checklist["not_placeholder"] = False

    failed_checks = [k for k, v in checklist.items() if not v]
    for k in failed_checks:
        findings_l.append(f"Checklist failed: {k}")

    pixels_ok = bool(vision_payload.get("passed")) and checklist.get("pixels_verified")
    forced_red = bool(ph) or not pixels_ok or not checklist.get("not_placeholder", False)

    av = (agent_verdict or "").upper().strip()
    if forced_red or av == "RED":
        verdict = CriticVerdict.RED
    elif not all(checklist.get(k, False) for k in required_keys):
        verdict = CriticVerdict.RED
    elif av == "YELLOW":
        verdict = CriticVerdict.YELLOW
    else:
        verdict = CriticVerdict.GREEN

    # Never GREEN without pixels
    if verdict == CriticVerdict.GREEN and not pixels_ok:
        verdict = CriticVerdict.RED
        findings_l.append("invariant: GREEN blocked without VisionBridge pass")

    escalate = verdict == CriticVerdict.RED
    summary = f"visual_critic {verdict.value}: {len(findings_l)} findings"
    result = VisualCriticResult(
        verdict=verdict,
        findings=findings_l,
        checklist=checklist,
        escalate=escalate,
        summary=summary,
    )
    result._extra_payload = {"vision": vision_payload, "pixels_required": False}  # type: ignore[attr-defined]
    return result


def run_soak(
    *,
    duration_sec: float = 30.0,
    errors: int = 0,
    stuck_pct: float = 0.0,
    notes: str = "",
    command: Optional[str] = None,
    workspace: Optional[str] = None,
    max_stuck_pct: float = 25.0,
    timeout_sec: int = 120,
) -> SoakResult:
    """
    Prefer agent-reported metrics from a real play/session.
    Optional command run (e.g. smoke script) contributes exit_code.
    """
    exit_code = None
    cmd = command or ""
    if command and workspace:
        try:
            proc = run_command_safely(
                command,
                cwd=str(Path(workspace).resolve()),
                timeout_sec=timeout_sec,
            )
            exit_code = proc.returncode
            if proc.returncode != 0:
                errors = max(errors, 1)
                notes = (notes + "\n" + (proc.stderr or proc.stdout or "")[-1500:]).strip()
        except subprocess.TimeoutExpired:
            exit_code = 124
            errors = max(errors, 1)
            notes = (notes + "\nsoak command timeout").strip()
        except Exception as exc:
            exit_code = 1
            errors = max(errors, 1)
            notes = (notes + f"\nsoak command error: {exc}").strip()

    passed = errors == 0 and stuck_pct <= max_stuck_pct and (exit_code is None or exit_code == 0)
    return SoakResult(
        passed=passed,
        duration_sec=float(duration_sec),
        errors=int(errors),
        stuck_pct=float(stuck_pct),
        notes=notes,
        command=cmd,
        exit_code=exit_code,
    )


def build_competitor_scan(
    queries: Sequence[str],
    competitors: Sequence[Dict[str, str]],
    min_required: int = 2,
) -> CompetitorScanResult:
    cleaned = []
    for c in competitors:
        name = (c.get("name") or "").strip()
        url = (c.get("url") or "").strip()
        if name or url:
            cleaned.append(
                {
                    "name": name or url,
                    "url": url,
                    "notes": (c.get("notes") or "").strip(),
                }
            )
    return CompetitorScanResult(
        queries=[q.strip() for q in queries if q and str(q).strip()],
        competitors=cleaned,
        min_required=min_required,
    )


def build_compare_delta(
    axes: Dict[str, float],
    *,
    still_losing: Optional[bool] = None,
    notes: str = "",
    best_competitor: str = "",
    lose_threshold: float = -0.5,
) -> CompareDeltaResult:
    """
    axes: positive = we win on that axis, negative = we lose.
    If still_losing omitted, infer from any axis <= lose_threshold.
    """
    if still_losing is None:
        still_losing = any(float(v) <= lose_threshold for v in axes.values()) if axes else True
    return CompareDeltaResult(
        axes={k: float(v) for k, v in axes.items()},
        still_losing=bool(still_losing),
        notes=notes,
        best_competitor=best_competitor,
    )


def next_ladder_level(current: Optional[str]) -> str:
    if not current:
        return LADDER_LEVELS[0]
    if current in LADDER_LEVELS:
        i = LADDER_LEVELS.index(current)
        return LADDER_LEVELS[min(i + 1, len(LADDER_LEVELS) - 1)]
    return LADDER_LEVELS[0]


def ladder_index(level: str) -> int:
    if level in LADDER_LEVELS:
        return LADDER_LEVELS.index(level)
    return 0


def _latest_by_source(state: TaskState, source: str) -> Optional[dict]:
    for ev in reversed(state.evidence):
        if (ev.payload or {}).get("source") == source:
            return {"id": ev.id, "type": ev.type.value, "payload": ev.payload, "summary": ev.summary}
    return None


def quality_claim_gates(
    state: TaskState,
    *,
    require_for_feature: bool = True,
    require_competitor_loop: bool = True,
    min_ladder: str = "L1_presence",
) -> tuple[bool, str]:
    """
    Extra claim gates for FEATURE (games, SaaS, accounting UI, etc.).
    Same ambition bar for all product software — competitor + ladder always.
    Visual soak/critic when needs_visual_loop (default for FEATURE UI).
    BUGFIX/REFACTOR skip unless metadata forces them.
    """
    from godkiller_mcp.search_gates import needs_visual_loop

    meta = state.handle.metadata or {}
    force = bool(meta.get("require_quality_loop"))
    kind = state.handle.kind

    needs = force or (require_for_feature and kind == TaskKind.FEATURE)
    if not needs:
        return True, "Quality loop not required for this kind."

    # Dissatisfaction loop — ALL features (accounting, ERP, games, SaaS)
    if require_competitor_loop:
        scan = _latest_by_source(state, "competitor_scan")
        if not scan or not scan["payload"].get("passed"):
            return (
                False,
                "Quality gate: competitor_scan required (web/social references) before claim "
                "(same bar for SaaS/accounting/games — beat named competitors).",
            )
        delta = _latest_by_source(state, "compare_delta")
        if not delta:
            return False, "Quality gate: compare_delta required after competitor_scan."
        if delta["payload"].get("still_losing"):
            return (
                False,
                "Dissatisfaction gate: still losing vs competitors — continue ladder, do not claim.",
            )
        if not delta["payload"].get("passed"):
            return False, "Quality gate: compare_delta did not pass."

    # Ladder floor
    level = meta.get("ambition_ladder") or "L0_core"
    if ladder_index(level) < ladder_index(min_ladder):
        return (
            False,
            f"Ambition ladder: at {level}, need at least {min_ladder} before claim "
            f"(advance via set_ambition_ladder / next phase).",
        )

    # Visual gates — UI products (incl. accounting dashboards); skip for surface=api/backend
    if needs_visual_loop(state, require_for_feature=require_for_feature):
        has_shot = EvidenceType.SCREENSHOT in state.evidence_types() or _latest_by_source(
            state, "capture_shot"
        )
        if not has_shot:
            return False, "Quality gate: capture_shot / SCREENSHOT required before claim."

        soak = _latest_by_source(state, "soak_run")
        if not soak or not soak["payload"].get("passed"):
            return False, "Quality gate: soak_run must pass before claim."

        critic = _latest_by_source(state, "visual_critic")
        if not critic:
            return False, "Quality gate: visual_critic required before claim."
        if critic["payload"].get("verdict") == CriticVerdict.RED.value:
            return (
                False,
                "Quality gate: visual_critic RED — fix placeholders or escalate frontier. "
                + critic["payload"].get("summary", ""),
            )
        if critic["payload"].get("verdict") != CriticVerdict.GREEN.value:
            return False, "Quality gate: visual_critic must be GREEN to claim (not YELLOW)."
        vision = critic["payload"].get("vision")
        if not isinstance(vision, dict) or not vision.get("passed"):
            return (
                False,
                "Quality gate: visual_critic GREEN requires VisionBridge pass on a real screenshot "
                "(text/checklist alone is not enough).",
            )
    return True, "Quality + dissatisfaction gates satisfied."
