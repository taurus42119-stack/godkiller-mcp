from __future__ import annotations

from godkiller_mcp.plan_os import PlanOS, NINE_STEPS
from godkiller_mcp.server import FACADE_ACTIONS, _tools
from godkiller_mcp.workflow_graph import WorkflowGraph
from godkiller_mcp.evidence_store import EvidenceStore


def test_facade_count_under_25():
    tools = _tools()
    assert 1 <= len(tools) <= 25
    assert "gk_phase" in {t.name for t in tools}
    assert "gk_memory" in {t.name for t in tools}


def test_nine_step_plan_validation():
    pos = PlanOS()
    incomplete = pos.validate({"goal": "x", "steps": {}})
    assert incomplete["valid"] is False
    assert len(incomplete["missing_steps"]) == len(NINE_STEPS)
    complete_steps = {k: f"done {k}" for k in NINE_STEPS}
    # 9-step alone is not enough — need visible ### Phase N
    no_phases = pos.validate({"goal": "ship CLI tool", "steps": complete_steps})
    assert no_phases["valid"] is False
    assert no_phases["phase_headings"]["ok"] is False
    complete = pos.validate(
        {
            "goal": "ship CLI tool",
            "steps": complete_steps,
            "phases": [
                {"name": "### Phase 1 — Implement parser"},
                {"name": "### Phase 2 — Verify tests"},
            ],
        }
    )
    assert complete["valid"] is True
    assert complete["allowed_to_edit"] is True
    assert complete["phase_headings"]["phase_count"] >= 2


def test_workflow_graph_query():
    store = EvidenceStore()
    state = store.open_task("bugfix", "fix divide by zero")
    store.submit_evidence(state.handle.task_id, "log", "repro noted", {"x": 1})
    g = WorkflowGraph(store).query_related(state.handle.task_id)
    assert g["node_count"] >= 2
    blocked = WorkflowGraph(store).what_blocked_claim_done(state.handle.task_id)
    assert blocked["blocked"] is True


def test_facade_action_maps_cover_core():
    assert "open" in FACADE_ACTIONS["gk_task"]
    assert "claim_done" in FACADE_ACTIONS["gk_phase"]
    assert "navigate" in FACADE_ACTIONS["gk_browser"]
    assert "semgrep" in FACADE_ACTIONS["gk_scan"]
