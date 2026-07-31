"""Fault probe + plan lock + strict governance."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.fault_probe import claim_fault_probe_gate, run_fault_probe
from godkiller_mcp.governance import plan_digest, require_task_for_privileged, require_valid_plan
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.plan_os import NINE_STEPS, PlanOS
from godkiller_mcp.schema import EvidenceType, TaskKind


def _full_plan(goal: str = "ship") -> dict:
    return {"goal": goal, "steps": {k: f"filled {k}" for k in NINE_STEPS}}


def test_fault_probe_kills_weak_equality(tmp_path: Path):
    mod = tmp_path / "calc.py"
    mod.write_text(
        "def add(a, b):\n    return a + b\n\ndef is_same(a, b):\n    return a == b\n",
        encoding="utf-8",
    )
    test = tmp_path / "test_calc.py"
    # Strong enough to kill +→- and ==→!= mutants
    test.write_text(
        "from calc import add, is_same\n"
        "def test_add():\n    assert add(2, 3) == 5\n"
        "def test_same():\n    assert is_same(1, 1) is True\n    assert is_same(1, 2) is False\n",
        encoding="utf-8",
    )
    report = run_fault_probe(
        workspace=tmp_path,
        target_file=mod,
        test_command="python -m pytest -q --tb=no",
        timeout_sec=30,
    )
    assert report.mutants_tried >= 1
    assert report.clean is True
    assert report.killed >= 1


def test_fault_probe_finds_survivor_when_tests_weak(tmp_path: Path):
    mod = tmp_path / "calc.py"
    mod.write_text("def is_same(a, b):\n    return a == b\n", encoding="utf-8")
    test = tmp_path / "test_calc.py"
    # Only asserts True path — flipping == to != may still pass if we only test equal pair wrong...
    # Actually is_same(1,1) with != returns False, assert True fails → killed.
    # Need a mutant that doesn't affect the only assertion: e.g. only test add-less file
    # with unused compare never called — use binop on dead code path.
    mod.write_text(
        "def unused(a, b):\n    return a + b\n\ndef ok():\n    return 1\n",
        encoding="utf-8",
    )
    test.write_text(
        "from calc import ok\ndef test_ok():\n    assert ok() == 1\n",
        encoding="utf-8",
    )
    report = run_fault_probe(
        workspace=tmp_path,
        target_file=mod,
        test_command="python -m pytest -q --tb=no",
        timeout_sec=30,
    )
    # +→- on unused() should SURVIVE because tests never call unused
    assert report.mutants_tried >= 1
    assert report.clean is False
    assert report.survivors


def test_claim_requires_fault_probe_evidence(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_FAULT_PROBE", "1")
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "g")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.EDIT_SAFE,
        "e",
        {"path": str(tmp_path / "x.py"), "server_authored": True},
        server_authored=True,
    )
    ok, reason = claim_fault_probe_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "fault_probe" in reason


def test_plan_lock_blocks_without_validation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GODKILLER_PLAN_LOCK", "1")
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.FEATURE, "g")
    ok, reason = require_valid_plan(state)
    assert ok is False
    assert "plan" in reason.lower()

    valid = PlanOS().validate(_full_plan())
    assert valid.get("valid") is True
    store.update_metadata(
        state.handle.task_id,
        {"plan_validation": {**valid, "digest": plan_digest(_full_plan())}, "plan_digest": plan_digest(_full_plan())},
    )
    ok2, _ = require_valid_plan(store.get(state.handle.task_id))
    assert ok2 is True


def test_strict_requires_task_id(monkeypatch):
    monkeypatch.setenv("GODKILLER_STRICT", "1")
    assert require_task_for_privileged("verify_bundle", {}) is not None
    assert require_task_for_privileged("verify_bundle", {"task_id": "t1"}) is None
    monkeypatch.delenv("GODKILLER_STRICT", raising=False)
    assert require_task_for_privileged("verify_bundle", {}) is None
