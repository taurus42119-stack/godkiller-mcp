"""Loop + phase-stall detector (Cody / Tree-SOP circuit breaker)."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional, Tuple

from godkiller_mcp.schema import Phase, PolicyAction


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ToolEvent:
    tool: str
    signature: str
    phase: Optional[str] = None
    at: str = field(default_factory=_utcnow)


@dataclass
class LoopVerdict:
    action: PolicyAction
    reason: str
    repeated_signature: Optional[str] = None
    same_phase_count: int = 0
    event_count: int = 0

    def to_dict(self) -> dict:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "repeated_signature": self.repeated_signature,
            "same_phase_count": self.same_phase_count,
            "event_count": self.event_count,
        }


class LoopDetector:
    """
    Tracks per-task tool signatures and phase visits.
    - identical signature N times in a row → REPLAN
    - same phase without advance for M events → ESCALATE_FRONTIER
    """

    def __init__(
        self,
        max_identical_streak: int = 3,
        max_events_same_phase: int = 8,
        history_size: int = 64,
    ):
        self.max_identical_streak = max_identical_streak
        self.max_events_same_phase = max_events_same_phase
        self.history_size = history_size
        self._events: Dict[str, Deque[ToolEvent]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._phase_anchor: Dict[str, Tuple[str, int]] = {}

    def record(
        self,
        task_id: str,
        tool: str,
        signature: str = "",
        phase: Optional[str | Phase] = None,
    ) -> LoopVerdict:
        phase_s = phase.value if isinstance(phase, Phase) else (phase or "")
        sig = signature or tool
        ev = ToolEvent(tool=tool, signature=sig, phase=phase_s or None)
        hist = self._events[task_id]
        hist.append(ev)

        # Identical streak
        streak = 0
        for e in reversed(hist):
            if e.signature == sig:
                streak += 1
            else:
                break
        if streak >= self.max_identical_streak:
            return LoopVerdict(
                action=PolicyAction.REPLAN,
                reason=(
                    f"Loop detector: tool signature repeated {streak}× "
                    f"('{sig}'). Stop and replan."
                ),
                repeated_signature=sig,
                event_count=len(hist),
            )

        # Phase stall
        if phase_s:
            anchor = self._phase_anchor.get(task_id)
            if anchor and anchor[0] == phase_s:
                count = anchor[1] + 1
            else:
                count = 1
            self._phase_anchor[task_id] = (phase_s, count)
            if count >= self.max_events_same_phase and phase_s not in (
                Phase.VERIFY.value,
                Phase.CLAIM_DONE.value,
                Phase.CLOSED.value,
            ):
                return LoopVerdict(
                    action=PolicyAction.ESCALATE_FRONTIER,
                    reason=(
                        f"Phase stall: stayed in '{phase_s}' for {count} tool events "
                        f"without progress. Escalate or replan."
                    ),
                    same_phase_count=count,
                    event_count=len(hist),
                )
            return LoopVerdict(
                action=PolicyAction.CONTINUE,
                reason="OK",
                same_phase_count=count,
                event_count=len(hist),
            )

        return LoopVerdict(
            action=PolicyAction.CONTINUE,
            reason="OK",
            event_count=len(hist),
        )

    def note_phase_advance(self, task_id: str, phase: str | Phase) -> None:
        phase_s = phase.value if isinstance(phase, Phase) else phase
        self._phase_anchor[task_id] = (phase_s, 0)

    def status(self, task_id: str) -> dict:
        hist = list(self._events.get(task_id, []))
        anchor = self._phase_anchor.get(task_id)
        return {
            "task_id": task_id,
            "event_count": len(hist),
            "recent": [
                {"tool": e.tool, "signature": e.signature, "phase": e.phase, "at": e.at}
                for e in hist[-10:]
            ],
            "phase_anchor": {"phase": anchor[0], "count": anchor[1]} if anchor else None,
        }
