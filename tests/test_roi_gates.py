"""ROI gates: write_guard ship claim, bugfix route, fail recipes, exhaustive symbol intel."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.memory_lessons import LessonMemory
from godkiller_mcp.roi_gates import (
    bugfix_edit_route_gate,
    claim_write_guard_gate,
    format_fail_recipes,
    inject_fail_recipes,
    symbol_intel_satisfied,
)
from godkiller_mcp.schema import EvidenceType, TaskKind


def test_write_guard_gate_blocks_ship(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.delenv("GODKILLER_WRITE_GUARD_PROVEN", raising=False)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    ok, reason = claim_write_guard_gate()
    assert ok is False
    assert "WRITE_GUARD_PROVEN" in reason


def test_write_guard_gate_passes_when_proven(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.setenv("GODKILLER_WRITE_GUARD_PROVEN", "1")
    ok, _ = claim_write_guard_gate()
    assert ok is True


def test_write_guard_gate_off_without_ship_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_WRITE_GUARD_PROVEN", raising=False)
    ok, _ = claim_write_guard_gate()
    assert ok is True


def test_bugfix_route_needs_search_and_blast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix crash")
    ok, reason = bugfix_edit_route_gate(state)
    assert ok is False
    assert "search" in reason.lower() or "auto-route" in reason.lower()

    store.submit_evidence(
        task_id=state.handle.task_id,
        evidence_type=EvidenceType.OTHER,
        summary="searches",
        payload={
            "source": "web_search",
            "queries": [
                "python crash traceback null",
                "fix attributeerror none type",
                "reproduce flake pytest race",
            ],
        },
        server_authored=True,
    )
    state = store.get(state.handle.task_id)
    ok2, reason2 = bugfix_edit_route_gate(state)
    assert ok2 is False
    assert "blast" in reason2.lower()

    store.submit_evidence(
        task_id=state.handle.task_id,
        evidence_type=EvidenceType.BLAST_RADIUS,
        summary="blast",
        payload={"symbol": "foo", "files": ["a.py"]},
        server_authored=True,
    )
    state = store.get(state.handle.task_id)
    ok3, _ = bugfix_edit_route_gate(state)
    assert ok3 is True


def test_symbol_intel_blocks_without_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GODKILLER_ALLOW_EXHAUSTIVE", raising=False)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    ok, reason = symbol_intel_satisfied({})
    assert ok is False
    assert "symbol" in reason.lower()


def test_symbol_intel_accepts_jcodemunch_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GODKILLER_ALLOW_EXHAUSTIVE", raising=False)
    ok, _ = symbol_intel_satisfied(
        {"jcodemunch_digest": "symbol FooBar in path/mod.py lines 10-40 blast"}
    )
    assert ok is True


def test_fail_recipes_inject_into_plan(tmp_path: Path) -> None:
    db = LessonMemory(tmp_path / "lessons.db")
    db.ingest_lesson(
        "default",
        "t1",
        "Do not claim done with stub TODO in main.go",
        tags=["fail", "hollow"],
        task_passed=False,
        mark_verified=True,
    )
    recipes = db.retrieve_fail_recipes("default", query="stub", limit=3)
    assert recipes["count_injected"] >= 1
    text = format_fail_recipes(recipes["injected"])
    plan = {"goal": "x", "steps": {k: "" for k in [
        "1_goal", "2_constraints", "3_stakeholders", "4_current_state",
        "5_options", "6_chosen_design", "7_blast_radius", "8_test_plan", "9_rollout_verify",
    ]}}
    out = inject_fail_recipes(plan, text)
    assert "Fail recipes" in out["steps"]["4_current_state"]
    assert out.get("fail_recipes_injected") is True
