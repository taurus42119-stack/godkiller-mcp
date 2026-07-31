"""Ship mode armor + exit checklist + forge blocks."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.exit_checklist import build_exit_checklist
from godkiller_mcp.fault_probe import claim_fault_probe_gate
from godkiller_mcp.freshness import evidence_fresh_against_disk
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.ship_mode import env_disables, ship_mode
from godkiller_mcp.server import FACADE_ACTIONS


def test_ship_mode_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    assert ship_mode() is True


def test_fault_probe_env_off_ignored_in_ship(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_FAULT_PROBE", "0")
    assert env_disables("GODKILLER_FAULT_PROBE") is False

    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    # Touch a py path so probe is required
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "edit",
        {"paths": [str(tmp_path / "a.py")], "source": "edit"},
    )
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")
    # Re-open with path in blast-style touch — hollow uses paths_touched
    # Ensure gate still demands probe (not skipped by FAULT_PROBE=0)
    ok, reason = claim_fault_probe_gate(store.get(state.handle.task_id), workspace=str(tmp_path))
    # Either no python paths counted, or probe required — must NOT say disabled via env alone
    assert "disabled via GODKILLER_FAULT_PROBE=0" not in reason
    if "no python" not in reason.lower():
        assert ok is False or "fault_probe" in reason.lower() or "clean" in reason.lower()


def test_freshness_env_off_ignored_in_ship(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_FRESHNESS", "0")
    assert env_disables("GODKILLER_FRESHNESS") is False
    ok, reason = evidence_fresh_against_disk({"passed": True}, workspace=".")
    assert ok is False
    assert "material_hash" in reason


def test_freshness_env_off_honored_only_in_relax(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    monkeypatch.setenv("GODKILLER_FRESHNESS", "0")
    assert env_disables("GODKILLER_FRESHNESS") is True
    ok, reason = evidence_fresh_against_disk({"passed": True}, workspace=".")
    assert ok is True


def test_cannot_forge_fault_probe_passing_test(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    with pytest.raises(PermissionError):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.PASSING_TEST,
            "fake",
            {"source": "fault_probe", "clean": True, "server_authored": True},
            server_authored=False,
        )


def test_exit_checklist_rejects_empty_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    report = build_exit_checklist(state)
    assert report["directive"] == "reject"
    assert report["status"] == "blocked"
    assert report["ship_mode"] is True
    assert report["blocking"]
    assert report["agent_role"]["may_decide_done"] is False


def test_facade_has_exit_checklist():
    assert FACADE_ACTIONS["gk_verify"]["exit"] == "exit_checklist"
