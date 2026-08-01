"""
Robust Slash Command & Epistemic Intent Router
Parses /ask, /plan, /debug, /ultradeep, /view, /verify and classifies complex task intent
"""

import re
from dataclasses import dataclass


@dataclass
class IntentClassification:
    command: str
    mode_name: str
    requires_search: bool
    requires_spec: bool
    requires_pytest: bool
    route_weight: float
    description: str

    @property
    def confidence(self) -> float:
        """Deprecated alias — fixed heuristic weight, not measured confidence."""
        return self.route_weight


class EpistemicRouter:
    """Classifies developer intent and routes to specialized AGENTS.md protocols"""

    COMMAND_PATTERNS = {
        "/ask": (r"^\s*/ask\b|interview|ask me|what is|how does", "INTERVIEW", False, False, False, "Exploration & Interview Protocol"),
        "/plan": (r"^\s*/plan\b|blueprint|spec|architecture|design plan", "PLANNING", True, True, False, "Blueprint & 9-Step Spec Protocol"),
        "/debug": (r"^\s*/debug\b|fix bug|root cause|traceback|error log|failing test", "DEBUGGING", True, True, True, "Systematic Root-Cause Debugging Protocol"),
        "/ultradeep": (r"^\s*/ultradeep\b|marathon|supreme|orchestrate|phase", "ULTRADEEP", True, True, True, "Ultradeep marathon + per-file think/plan/edit protocol"),
        "/view": (r"^\s*/view\b|lit review|literature review|adversarial review|critique paper|research critique", "VIEW", True, True, False, "Adversarial Research Planning Protocol"),
        "/verify": (r"^\s*/verify\b|rubric|claim done|empirical proof|pytest check", "VERIFICATION", False, False, True, "Empirical Pytest Proof Protocol"),
        "/jury": (r"^\s*/jury\b|ship review|ตรวจเข้ม|go-no-go|beta audit|harsh review", "JURY", True, True, True, "Harsh Beta ship jury (evidence A–E; cold path)"),
    }

    def route_intent(self, prompt: str) -> IntentClassification:
        prompt_clean = prompt.strip().lower()

        # Check explicit slash command triggers
        for cmd, (pattern, mode, req_search, req_spec, req_test, desc) in self.COMMAND_PATTERNS.items():
            if re.search(pattern, prompt_clean, re.IGNORECASE):
                return IntentClassification(
                    command=cmd,
                    mode_name=mode,
                    requires_search=req_search,
                    requires_spec=req_spec,
                    requires_pytest=req_test,
                    route_weight=0.95,
                    description=desc
                )

        # Implicit intent fallback
        if "bug" in prompt_clean or "fix" in prompt_clean or "error" in prompt_clean:
            return IntentClassification(
                command="/debug",
                mode_name="DEBUGGING",
                requires_search=True,
                requires_spec=True,
                requires_pytest=True,
                route_weight=0.80,
                description="Implicit Debugging Intent Detected"
            )

        return IntentClassification(
            command="/plan",
            mode_name="PLANNING",
            requires_search=True,
            requires_spec=True,
            requires_pytest=False,
            route_weight=0.70,
            description="Implicit Planning & Blueprint Intent Detected"
        )
