"""9-step Plan OS: template + validation before code mutation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


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

    def template(self, goal: str = "") -> Dict[str, Any]:
        return {
            "goal": goal or "<describe outcome>",
            "steps": {k: "" for k in NINE_STEPS},
            "required_keys": list(NINE_STEPS),
            "rule": "All 9 steps must be non-empty before FIX phase / edit_safe is allowed.",
        }

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

        return PlanSpec(goal=goal, phases=phases, steps=steps)

    def from_dict(self, data: Dict[str, Any]) -> PlanSpec:
        steps = data.get("steps") or {}
        return PlanSpec(goal=str(data.get("goal") or ""), steps={k: str(steps.get(k) or "") for k in NINE_STEPS})

    def validate(self, plan: PlanSpec | Dict[str, Any] | str) -> Dict[str, Any]:
        if isinstance(plan, str):
            spec = self.load_plan(plan)
        elif isinstance(plan, dict):
            spec = self.from_dict(plan)
        else:
            spec = plan
        missing = spec.missing_steps()
        return {
            "valid": not missing,
            "goal": spec.goal,
            "missing_steps": missing,
            "completed_steps": [k for k in NINE_STEPS if k not in missing],
            "allowed_to_edit": not missing,
            "reason": (
                "9-step plan complete"
                if not missing
                else f"Plan incomplete; missing: {', '.join(missing)}"
            ),
        }
