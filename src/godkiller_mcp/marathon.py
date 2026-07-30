"""Marathon Relay — 24h-capable progress across short Antigravity sessions.

Externalizes state so /ultradeep can wake, do ONE phase, save, and resume
without relying on chat context (Anthropic-style initializer + coding relay).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from godkiller_mcp.schema import Phase, TaskKind, new_id


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class MarathonState(BaseModel):
    slug: str
    task_id: Optional[str] = None
    kind: TaskKind = TaskKind.FEATURE
    goal: str = ""
    plan_path: Optional[str] = None
    current_plan_phase: int = 1
    kernel_phase: Phase = Phase.OPEN
    evidence_ids: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    blockers: List[str] = Field(default_factory=list)
    failure_streak: int = 0
    session_count: int = 0
    last_handoff: str = ""
    created_at: str = Field(default_factory=_utcnow)
    updated_at: str = Field(default_factory=_utcnow)
    closed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MarathonRelay:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, slug: str) -> Path:
        d = self.root / slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def state_path(self, slug: str) -> Path:
        return self._dir(slug) / "STATE.json"

    def progress_path(self, slug: str) -> Path:
        return self._dir(slug) / "PROGRESS.md"

    def init(
        self,
        slug: str,
        goal: str,
        kind: TaskKind | str = TaskKind.FEATURE,
        plan_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> MarathonState:
        kind_e = TaskKind(kind) if isinstance(kind, str) else kind
        state = MarathonState(
            slug=slug,
            goal=goal,
            kind=kind_e,
            plan_path=plan_path,
            task_id=task_id or new_id("task"),
            session_count=1,
            last_handoff="Initialized marathon. Next: Phase 1 research/reproduce.",
        )
        self._write(state)
        return state

    def load(self, slug: str) -> MarathonState:
        path = self.state_path(slug)
        if not path.exists():
            raise FileNotFoundError(f"No marathon state for slug={slug}")
        return MarathonState.model_validate_json(path.read_text(encoding="utf-8"))

    def save(
        self,
        slug: str,
        *,
        task_id: Optional[str] = None,
        kernel_phase: Optional[Phase | str] = None,
        current_plan_phase: Optional[int] = None,
        evidence_ids: Optional[List[str]] = None,
        search_queries: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None,
        failure_streak: Optional[int] = None,
        last_handoff: Optional[str] = None,
        closed: Optional[bool] = None,
        bump_session: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MarathonState:
        state = self.load(slug)
        if task_id is not None:
            state.task_id = task_id
        if kernel_phase is not None:
            state.kernel_phase = Phase(kernel_phase) if isinstance(kernel_phase, str) else kernel_phase
        if current_plan_phase is not None:
            state.current_plan_phase = current_plan_phase
        if evidence_ids is not None:
            # merge unique
            merged = list(dict.fromkeys([*state.evidence_ids, *evidence_ids]))
            state.evidence_ids = merged
        if search_queries is not None:
            merged_q = list(dict.fromkeys([*state.search_queries, *search_queries]))
            state.search_queries = merged_q
        if blockers is not None:
            state.blockers = blockers
        if failure_streak is not None:
            state.failure_streak = failure_streak
        if last_handoff is not None:
            state.last_handoff = last_handoff
        if closed is not None:
            state.closed = closed
        if metadata:
            state.metadata.update(metadata)
        if bump_session:
            state.session_count += 1
        state.updated_at = _utcnow()
        self._write(state)
        return state

    def require_search_gate(
        self,
        slug: str,
        min_queries: Optional[int] = None,
    ) -> tuple[bool, str]:
        from godkiller_mcp.search_gates import min_queries_for_kind

        state = self.load(slug)
        need = min_queries if min_queries is not None else min_queries_for_kind(state.kind)
        n = len(state.search_queries)
        if n < need:
            return (
                False,
                f"Forced search gate: need ≥{need} search queries; have {n}. "
                "Local skills do NOT waive search_web.",
            )
        return True, f"Search gate OK ({n} queries)."

    def next_wake_prompt(self, slug: str) -> str:
        state = self.load(slug)
        nxt = state.current_plan_phase + (0 if state.closed else 0)
        # After save of completed phase, caller should bump plan phase; prompt uses current+1 if not closed
        phase = state.current_plan_phase if not state.closed else state.current_plan_phase
        if state.closed:
            return f"/verify task={slug} (marathon closed)"
        return (
            f"/ultradeep Phase {phase} continue task={slug}. "
            f"Load marathon_load_progress. Kernel phase={state.kernel_phase.value}. "
            f"Handoff: {state.last_handoff}"
        )

    def _write(self, state: MarathonState) -> None:
        self.state_path(state.slug).write_text(state.model_dump_json(indent=2), encoding="utf-8")
        self.progress_path(state.slug).write_text(self._progress_md(state), encoding="utf-8")

    def _progress_md(self, state: MarathonState) -> str:
        searches = [f"- {q}" for q in state.search_queries] or ["- (none yet — GATE WILL BLOCK)"]
        evidence = [f"- `{e}`" for e in state.evidence_ids] or ["- (none)"]
        blockers = [f"- {b}" for b in state.blockers] or ["- (none)"]
        lines = [
            f"# Marathon Progress — `{state.slug}`",
            "",
            f"- **Goal:** {state.goal}",
            f"- **Kind:** {state.kind.value}",
            f"- **Kernel task_id:** `{state.task_id}`",
            f"- **Plan phase:** {state.current_plan_phase}",
            f"- **Kernel phase:** `{state.kernel_phase.value}`",
            f"- **Sessions:** {state.session_count}",
            f"- **Failure streak:** {state.failure_streak}",
            f"- **Closed:** {state.closed}",
            f"- **Updated:** {state.updated_at}",
            "",
            "## Handoff (read this next session)",
            state.last_handoff or "(none)",
            "",
            "## Search queries (forced epistemics)",
            *searches,
            "",
            "## Evidence ids",
            *evidence,
            "",
            "## Blockers",
            *blockers,
            "",
            "## Next wake",
            f"`{self.next_wake_prompt(state.slug)}`",
            "",
        ]
        return "\n".join(lines)

    def list_slugs(self) -> List[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and (p / "STATE.json").exists())
