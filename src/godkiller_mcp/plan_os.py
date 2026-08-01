"""9-step Plan OS: template + validation before code mutation.

UI/web/game plans must also declare playtest→capture→inspect→recheck phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from godkiller_mcp.phase_heading_gate import evaluate_phase_heading_gate
from godkiller_mcp.ui_plan_phases import (
    CANONICAL_UI_PHASES,
    detect_ui_plan_work,
    evaluate_ui_plan_phases,
    format_canonical_ui_phases_markdown,
)


NINE_STEPS = [
    "1_goal",
    "2_constraints",
    "3_stakeholders",
    "4_current_state",
    "5_options",
    "6_chosen_design",
    "7_blast_radius",
    "8_test_plan",
    "9_rollout_verify",
]


@dataclass
class PlanPhase:
    name: str
    description: str = ""
    completed: bool = False


@dataclass
class PlanSpec:
    goal: str
    phases: List[PlanPhase] = field(default_factory=list)
    steps: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    ui_work: Optional[bool] = None
    extra_text: str = ""

    def missing_steps(self) -> List[str]:
        missing = []
        for key in NINE_STEPS:
            val = (self.steps.get(key) or "").strip()
            if not val:
                missing.append(key)
        return missing

    def is_complete(self) -> bool:
        return not self.missing_steps()


class PlanOS:
    def __init__(self, plan_file: Optional[str] = None):
        self.plan_file = plan_file

    def template(self, goal: str = "", *, ui_work: Optional[bool] = None) -> Dict[str, Any]:
        steps = {k: "" for k in NINE_STEPS}
        ui = detect_ui_plan_work(goal=goal or "", ui_work=ui_work)
        out: Dict[str, Any] = {
            "goal": goal or "<describe outcome>",
            "steps": steps,
            "required_keys": list(NINE_STEPS),
            "rule": "All 9 steps must be non-empty before FIX phase / edit_safe is allowed.",
            "ui_work_detected": ui,
        }
        if ui:
            out["ui_required_phases"] = [dict(p) for p in CANONICAL_UI_PHASES]
            out["ui_phases_markdown"] = format_canonical_ui_phases_markdown(start_n=1)
            out["ui_rule"] = (
                "UI/web/game plans MUST use visible ### Phase N — Title headings "
                "(never bare ### <Module/System> titles). Include trailing phases: "
                "playtest → capture → inspect → recheck. Keywords only in 8_test_plan do not count."
            )
            steps["8_test_plan"] = (
                "MUST include: (1) long real playtest/soak while app runs; "
                "(2) ~8–10 gk_evidence.visual_step captures; "
                "(3) visual_critic/VisionBridge inspect each shot; "
                "(4) visual recheck pass. Then unit/integration tests."
            )
        return out

    def load_plan(self, content: str) -> PlanSpec:
        phases: List[PlanPhase] = []
        goal = "General Plan"
        steps: Dict[str, str] = {}

        current_key: Optional[str] = None
        buf: List[str] = []
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("# Goal:"):
                goal = line_str.replace("# Goal:", "").strip()
            elif line_str.startswith("- Phase") or line_str.startswith("### Phase"):
                completed = "[x]" in line_str
                phases.append(PlanPhase(name=line_str, description="", completed=completed))
            elif line_str.startswith("## "):
                if current_key and buf:
                    steps[current_key] = "\n".join(buf).strip()
                title = line_str[3:].strip().lower().replace(" ", "_")
                matched = None
                for key in NINE_STEPS:
                    short = key.split("_", 1)[1]
                    if short in title or key in title:
                        matched = key
                        break
                current_key = matched
                buf = []
            elif current_key is not None:
                buf.append(line)
        if current_key and buf:
            steps[current_key] = "\n".join(buf).strip()

        return PlanSpec(goal=goal, phases=phases, steps=steps, extra_text=content)

    def from_dict(self, data: Dict[str, Any]) -> PlanSpec:
        steps_in = data.get("steps") or {}
        steps = {k: str(steps_in.get(k) or "") for k in NINE_STEPS}
        phases_raw = data.get("phases") or []
        phases: List[PlanPhase] = []
        for p in phases_raw:
            if isinstance(p, dict):
                phases.append(
                    PlanPhase(
                        name=str(p.get("name") or p.get("title") or ""),
                        description=str(p.get("description") or p.get("dod") or ""),
                        completed=bool(p.get("completed")),
                    )
                )
            elif isinstance(p, str):
                phases.append(PlanPhase(name=p))
        ui_flag = data.get("ui_work")
        if ui_flag is not None:
            ui_flag = bool(ui_flag)
        return PlanSpec(
            goal=str(data.get("goal") or ""),
            steps=steps,
            phases=phases,
            metadata=dict(data.get("metadata") or {}),
            ui_work=ui_flag,
            extra_text=str(data.get("content") or data.get("markdown") or ""),
        )

    def validate(
        self,
        plan: PlanSpec | Dict[str, Any] | str,
        *,
        ui_work: Optional[bool] = None,
        metadata: Optional[dict] = None,
    ) -> Dict[str, Any]:
        if isinstance(plan, str):
            spec = self.load_plan(plan)
        elif isinstance(plan, dict):
            spec = self.from_dict(plan)
        else:
            spec = plan

        missing = spec.missing_steps()
        meta = {**(spec.metadata or {}), **(metadata or {})}
        flag = ui_work if ui_work is not None else spec.ui_work

        phase_blob_parts = [spec.extra_text or ""]
        for p in spec.phases:
            phase_blob_parts.append(p.name or "")
            phase_blob_parts.append(p.description or "")
        # steps may embed phased markdown under 8_test_plan
        for key in ("8_test_plan", "9_rollout_verify", "6_chosen_design"):
            phase_blob_parts.append(spec.steps.get(key) or "")
        phase_blob = "\n".join(phase_blob_parts)

        heading_gate = evaluate_phase_heading_gate(
            text=phase_blob,
            phases=spec.phases,
            min_phases=int(meta.get("min_plan_phases") or 2),
            metadata=meta,
        )
        ui_gate = evaluate_ui_plan_phases(
            goal=spec.goal,
            steps=spec.steps,
            phases=spec.phases,
            metadata=meta,
            ui_work=flag,
            extra_text=phase_blob,
        )
        ui_ok = bool(ui_gate.get("ok"))
        head_ok = bool(heading_gate.get("ok"))
        valid = (not missing) and ui_ok and head_ok
        reasons: List[str] = []
        if missing:
            reasons.append(f"Plan incomplete; missing: {', '.join(missing)}")
        if not head_ok:
            reasons.append(str(heading_gate.get("reason") or "Phase headings missing"))
        if not ui_ok:
            reasons.append(str(ui_gate.get("reason") or "UI phases missing"))
        if not reasons:
            bits = ["9-step plan complete", "### Phase N headings OK"]
            if ui_gate.get("ui_work"):
                bits.append("UI playtest phases")
            reasons.append(" + ".join(bits))

        return {
            "valid": valid,
            "goal": spec.goal,
            "missing_steps": missing,
            "completed_steps": [k for k in NINE_STEPS if k not in missing],
            "allowed_to_edit": valid,
            "phase_headings": heading_gate,
            "ui_plan": ui_gate,
            "reason": " | ".join(reasons),
        }
