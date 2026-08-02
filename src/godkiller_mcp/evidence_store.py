"""In-memory Evidence Graph store keyed by TaskHandle (server-side state)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write via same-dir temp + os.replace so a crash mid-write keeps the prior file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

from godkiller_mcp.schema import (
    Evidence,
    EvidenceType,
    Hypothesis,
    Phase,
    TaskHandle,
    TaskKind,
    TaskState,
    new_id,
)

# Client tools may not forge these; only server handlers with server_authored=True.
SERVER_ONLY_EVIDENCE: Set[EvidenceType] = {
    EvidenceType.PASSING_TEST,
    EvidenceType.BLAST_RADIUS,
    EvidenceType.EDIT_SAFE,
}

# Payload sources that only the server tools may mint (any evidence type).
from godkiller_mcp.evidence_integrity import ARMOR_SOURCES  # noqa: E402


class EvidenceStore:
    def __init__(self, persist_dir: Optional[str | Path] = None):
        self._tasks: Dict[str, TaskState] = {}
        self.persist_dir = Path(persist_dir) if persist_dir else None
        self._seal_key: Optional[bytes] = None
        if self.persist_dir:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            from godkiller_mcp.evidence_integrity import load_or_create_seal_key

            self._seal_key = load_or_create_seal_key(self.persist_dir)

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
        *,
        server_authored: bool = False,
    ) -> Evidence:
        state = self.get(task_id)
        if state.closed:
            raise RuntimeError("Task is closed; cannot submit evidence.")

        et = EvidenceType(evidence_type) if isinstance(evidence_type, str) else evidence_type
        payload = dict(payload or {})

        if et in SERVER_ONLY_EVIDENCE and not server_authored:
            raise PermissionError(
                f"Evidence type '{et.value}' is server-authored only "
                "(use verify_bundle / blast_radius / check_edit_safe tools)."
            )

        # Client must never set server_authored / armor source on any type (closes LOG forge)
        if not server_authored:
            src = str(payload.get("source") or "")
            if src in ARMOR_SOURCES:
                raise PermissionError(
                    f"Forged armor source={src!r} on {et.value} is not allowed — use server tools."
                )
            if payload.get("server_authored") is True:
                raise PermissionError(
                    "Client cannot set server_authored=true on evidence payloads."
                )
            payload.pop("server_authored", None)

        # Block forged verify_bundle success via EXIT_CODE submit
        if (
            not server_authored
            and et == EvidenceType.EXIT_CODE
            and (
                payload.get("source") == "verify_bundle"
                or payload.get("passed") is True
            )
        ):
            raise PermissionError(
                "Forged verify_bundle / passing EXIT_CODE evidence is not allowed via submit_evidence."
            )

        if server_authored:
            payload["server_authored"] = True
            src = str(payload.get("source") or "")
            if src in ARMOR_SOURCES and self._seal_key:
                from godkiller_mcp.evidence_integrity import attach_seal

                payload = attach_seal(task_id, payload, self._seal_key)

        ev = Evidence(
            task_id=task_id,
            type=et,
            summary=summary,
            payload=payload,
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
            statement=claim,
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
        if state.closed:
            raise RuntimeError("Task is closed; cannot update metadata.")
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
        from godkiller_mcp.file_lock import path_lock

        path = self.persist_dir / f"{state.handle.task_id}.json"
        lock = self.persist_dir / "tasks.lock"
        with path_lock(lock, timeout_sec=30.0):
            atomic_write_text(path, state.model_dump_json(indent=2))

    def _load(self, task_id: str) -> Optional[TaskState]:
        if not self.persist_dir:
            return None
        from godkiller_mcp.file_lock import path_lock

        path = self.persist_dir / f"{task_id}.json"
        lock = self.persist_dir / "tasks.lock"
        with path_lock(lock, timeout_sec=30.0):
            if not path.exists():
                return None
            state = TaskState.model_validate_json(path.read_text(encoding="utf-8"))
        # B5: drop armor evidences whose seals do not match (disk forge)
        if self._seal_key:
            from godkiller_mcp.evidence_integrity import scrub_forged_armor

            dropped = scrub_forged_armor(state, self._seal_key)
            if dropped:
                self._persist(state)
        return state

    def dump_graph(self, task_id: str) -> dict:
        state = self.get(task_id)
        return json.loads(state.model_dump_json())
