"""Task → Phase → Evidence → Hypothesis → Lesson workflow graph queries."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import Phase


class WorkflowGraph:
    def __init__(self, store: EvidenceStore):
        self.store = store

    def query_related(self, task_id: str) -> Dict[str, Any]:
        state = self.store.get(task_id)
        nodes = [
            {"id": state.handle.task_id, "type": "task", "label": state.handle.goal, "phase": state.handle.phase.value},
        ]
        edges: List[Dict[str, str]] = []
        for ph in state.phase_history or []:
            pid = f"phase:{ph.value}"
            nodes.append({"id": pid, "type": "phase", "label": ph.value})
            edges.append({"from": state.handle.task_id, "to": pid, "rel": "advanced_to"})
        for ev in state.evidences:
            nodes.append({"id": ev.id, "type": "evidence", "label": ev.summary, "evidence_type": ev.type.value})
            edges.append({"from": state.handle.task_id, "to": ev.id, "rel": "has_evidence"})
        for hyp in state.hypotheses:
            nodes.append({"id": hyp.id, "type": "hypothesis", "label": hyp.statement})
            edges.append({"from": state.handle.task_id, "to": hyp.id, "rel": "has_hypothesis"})
            for ref in hyp.support_refs:
                edges.append({"from": hyp.id, "to": ref, "rel": "supported_by"})
            for ref in hyp.refute_refs:
                edges.append({"from": hyp.id, "to": ref, "rel": "refuted_by"})
        return {
            "task_id": task_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def what_blocked_claim_done(self, task_id: str, policy_reason: str = "") -> Dict[str, Any]:
        state = self.store.get(task_id)
        blockers: List[str] = []
        if state.handle.phase not in (Phase.VERIFY, Phase.CLAIM_DONE, Phase.CLOSED):
            blockers.append(f"phase_not_ready:{state.handle.phase.value}")
        types = {t.value for t in state.evidence_types()}
        if "passing_test" not in types and "exit_code" not in types:
            blockers.append("missing_verify_evidence")
        if state.handle.kind.value == "feature" and "screenshot" not in types and "ui_journey" not in types:
            blockers.append("missing_ui_proof")
        plan = (state.handle.metadata or {}).get("plan_validation") or {}
        if plan and not plan.get("valid", True):
            blockers.append("incomplete_nine_step_plan")
        if policy_reason:
            blockers.append(f"policy:{policy_reason}")
        return {
            "task_id": task_id,
            "blocked": bool(blockers),
            "blockers": blockers,
            "phase": state.handle.phase.value,
            "evidence_types": sorted(types),
        }

    def upsert_episode(self, task_id: str, summary: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        state = self.store.get(task_id)
        episodes = list((state.handle.metadata or {}).get("episodes") or [])
        episode = {
            "summary": summary,
            "payload": payload or {},
            "phase": state.handle.phase.value,
        }
        episodes.append(episode)
        self.store.update_metadata(task_id, {"episodes": episodes[-50:]})
        return {"stored": True, "episode_count": len(episodes[-50:]), "latest": episode}
