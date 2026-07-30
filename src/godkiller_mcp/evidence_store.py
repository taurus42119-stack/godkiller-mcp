"""In-memory Evidence Graph store keyed by TaskHandle (server-side state)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from godkiller.schema import (
    Evidence,
    EvidenceType,
    Hypothesis,
    Phase,
    TaskHandle,
    TaskKind,
    TaskState,
    new_id,
)


class EvidenceStore:
    def __init__(self, persist_dir: Optional[str | Path] = None):
        self._tasks: Dict[str, TaskState] = {}
        self.persist_dir = Path(persist_dir) if persist_dir else None
        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)

    def open_task(
        self,
        kind: TaskKind | str,
        goal: str,
        project_id: str = "default",
        metadata: Optional[dict] = None,
    ) -> TaskState:
        kind_enum = TaskKind(kind) if isinstance(kind, str) else kind
        rubric_id = {
            TaskKind.BUGFIX: "bugfix_v1",
            TaskKind.FEATURE: "feature_v1",
            TaskKind.REFACTOR: "refactor_v1",
        }[kind_enum]
        handle = TaskHandle(
            task_id=new_id("task"),
            kind=kind_enum,
            goal=goal,
            project_id=project_id,
            phase=Phase.OPEN,
            rubric_id=rubric_id,
            metadata=metadata or {},
        )
        state = TaskState(handle=handle)
        self._tasks[handle.task_id] = state
        self._persist(state)
        return state

    def get(self, task_id: str) -> TaskState:
        if task_id not in self._tasks:
            loaded = self._load(task_id)
            if loaded is None:
                raise KeyError(f"Unknown task handle: {task_id}")
            self._tasks[task_id] = loaded
        return self._tasks[task_id]

    def list_tasks(self) -> List[TaskHandle]:
        return [s.handle for s in self._tasks.values()]

    def submit_evidence(
        self,
        task_id: str,
        evidence_type: EvidenceType | str,
        summary: str,
        payload: Optional[dict] = None,
        uri: Optional[str] = None,
        contradicts: Optional[List[str]] = None,
    ) -> Evidence:
        state = self.get(task_id)
        if state.closed:
            raise RuntimeError("Task is closed; cannot submit evidence.")
        ev = Evidence(
            task_id=task_id,
            type=EvidenceType(evidence_type) if isinstance(evidence_type, str) else evidence_type,
            summary=summary,
            payload=payload or {},
            uri=uri,
            contradicts=contradicts or [],
        )
        state.evidence.append(ev)
        self._persist(state)
        return ev

    def propose_hypothesis(
        self,
        task_id: str,
        claim: str,
        support_refs: Optional[List[str]] = None,
        refute_refs: Optional[List[str]] = None,
    ) -> Hypothesis:
        state = self.get(task_id)
        if state.closed:
            raise RuntimeError("Task is closed; cannot propose hypothesis.")
        hyp = Hypothesis(
            task_id=task_id,
            claim=claim,
            support_refs=support_refs or [],
            refute_refs=refute_refs or [],
        )
        state.hypotheses.append(hyp)
        self._persist(state)
        return hyp

    def assert_phase(self, task_id: str, phase: Phase | str) -> TaskState:
        state = self.get(task_id)
        if state.closed:
            raise RuntimeError("Task is closed.")
        phase_enum = Phase(phase) if isinstance(phase, str) else phase
        order = [
            Phase.OPEN,
            Phase.REPRODUCE,
            Phase.HYPOTHESIZE,
            Phase.LOCALIZE,
            Phase.FIX,
            Phase.VERIFY,
            Phase.CLAIM_DONE,
            Phase.CLOSED,
        ]
        current_idx = order.index(state.handle.phase)
        next_idx = order.index(phase_enum)
        # Allow same phase re-assert; block skipping more than one forward step
        if next_idx > current_idx + 1:
            raise ValueError(
                f"Illegal phase jump: {state.handle.phase.value} -> {phase_enum.value}. "
                "Advance one phase at a time."
            )
        if next_idx < current_idx and phase_enum != Phase.REPRODUCE:
            # Allow rollback only to reproduce (replan)
            raise ValueError(
                f"Illegal phase rollback: {state.handle.phase.value} -> {phase_enum.value}."
            )
        state.handle.phase = phase_enum
        state.phase_history.append(phase_enum)
        self._persist(state)
        return state

    def update_metadata(self, task_id: str, patch: dict) -> TaskState:
        state = self.get(task_id)
        state.handle.metadata.update(patch or {})
        self._persist(state)
        return state

    def mark_closed(self, task_id: str) -> TaskState:
        state = self.get(task_id)
        state.handle.phase = Phase.CLOSED
        state.phase_history.append(Phase.CLOSED)
        state.closed = True
        state.claim_allowed = True
        self._persist(state)
        return state

    def _persist(self, state: TaskState) -> None:
        if not self.persist_dir:
            return
        path = self.persist_dir / f"{state.handle.task_id}.json"
        path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    def _load(self, task_id: str) -> Optional[TaskState]:
        if not self.persist_dir:
            return None
        path = self.persist_dir / f"{task_id}.json"
        if not path.exists():
            return None
        return TaskState.model_validate_json(path.read_text(encoding="utf-8"))

    def dump_graph(self, task_id: str) -> dict:
        state = self.get(task_id)
        return json.loads(state.model_dump_json())
