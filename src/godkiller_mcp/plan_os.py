"""Plan OS: Multi-phase planning and execution orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PlanPhase:
    name: str
    description: str
    completed: bool = False


@dataclass
class PlanSpec:
    goal: str
    phases: List[PlanPhase] = field(default_factory=list)


class PlanOS:
    def __init__(self, plan_file: Optional[str | Path] = None):
        self.plan_file = Path(plan_file) if plan_file else None

    def load_plan(self, content: str) -> PlanSpec:
        phases: List[PlanPhase] = []
        goal = "General Plan"

        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("# Goal:"):
                goal = line_str.replace("# Goal:", "").strip()
            elif line_str.startswith("- Phase") or line_str.startswith("### Phase"):
                completed = "[x]" in line_str
                phases.append(PlanPhase(name=line_str, description="", completed=completed))

        return PlanSpec(goal=goal, phases=phases)
