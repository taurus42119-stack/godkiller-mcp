"""Epistemic Task Router: Automatic task classification and route selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class RouteDecision:
    task_kind: str
    recommended_mode: str
    confidence: float


class EpistemicRouter:
    def route(self, task_description: str) -> RouteDecision:
        desc_lower = task_description.lower()

        if "bug" in desc_lower or "fix" in desc_lower or "error" in desc_lower:
            return RouteDecision(
                task_kind="bugfix", recommended_mode="debug", confidence=0.9
            )
        elif "feature" in desc_lower or "build" in desc_lower or "add" in desc_lower:
            return RouteDecision(
                task_kind="feature", recommended_mode="plan", confidence=0.85
            )
        else:
            return RouteDecision(
                task_kind="refactor", recommended_mode="ultradeep", confidence=0.8
            )
