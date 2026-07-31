"""Adversarial critic pack — C1–C6 + pointer to critic-hunt B1–B5.

B1–B5 live proofs are in ``test_critic_hunt_b1_b5.py`` (same suite, not marketing-only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.fault_probe import claim_fault_probe_gate
from godkiller_mcp.freshness import material_hash
from godkiller_mcp.governance import plan_always_required, require_valid_plan
from godkiller_mcp.hollow_surface import claim_hollow_gate
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.verify_bundle import (
    VerifyBundleRunner,
    is_test_verify_command,
    task_has_passing_verify_bundle,
)


def test_c1_cannot_forge_verify_via_log(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    mat = material_hash([], workspace=tmp_path)
    with pytest.raises(PermissionError):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.LOG,
            "fake",
            {
                "source": "verify_bundle",
                "passed": True,
                "server_authored": True,
                "result_digest": "a" * 64,
                "material_hash": mat["material_hash"],
                "material_files": [],
                "cwd": str(tmp_path),
                "is_test_suite": True,
                "commands": ["python -m pytest -q"],
            },
            server_authored=False,
        )


def test_c1_cannot_forge_probe_via_other(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    with pytest.raises(PermissionError):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.OTHER if hasattr(EvidenceType, "OTHER") else EvidenceType.LOG,
            "fake",
            {"source": "fault_probe", "clean": True, "server_authored": True, "mutants_tried": 3},
            server_authored=False,
        )


def test_c3_vacuous_hollow_blocks_bugfix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    ok, reason, _ = claim_hollow_gate(state)
    assert ok is False
    assert "no edit paths" in reason.lower() or "cannot claim" in reason.lower()


def test_c3_vacuous_probe_blocks_bugfix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    ok, reason = claim_fault_probe_gate(state)
    assert ok is False
    assert "no python" in reason.lower() or "fault_probe" in reason.lower()


def test_c4_lint_is_not_claim_grade(tmp_path: Path):
    assert is_test_verify_command("ruff check .") is False
    assert is_test_verify_command("python -m pytest -q") is True
    (tmp_path / "test_ok.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    # Simulate lint-only receipt attached as EXIT_CODE (what dispatch does now)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    mat = material_hash([tmp_path], workspace=tmp_path)
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.EXIT_CODE,
        "lint",
        {
            "source": "verify_bundle",
            "passed": True,
            "server_authored": True,
            "result_digest": "b" * 64,
            "material_hash": mat["material_hash"],
            "material_files": mat["files"],
            "cwd": str(tmp_path),
            "is_test_suite": False,
            "commands": ["ruff", "check", "."],
        },
        server_authored=True,
    )
    ok, reason = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok is False
    assert "lint" in reason.lower() or "missing" in reason.lower() or "claim-grade" in reason.lower()


def test_c4_pytest_is_claim_grade(tmp_path: Path):
    (tmp_path / "test_ok.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    result = VerifyBundleRunner(timeout_sec=30).run(tmp_path, ["python -m pytest -q"])
    assert result.passed
    assert result.is_test_suite is True
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    mat = material_hash([tmp_path], workspace=tmp_path)
    payload = result.to_payload()
    payload["material_hash"] = mat["material_hash"]
    payload["material_files"] = mat["files"]
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.PASSING_TEST,
        result.summary,
        payload,
        server_authored=True,
    )
    ok, reason = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok, reason


def test_c6_plan_lock_env_ignored_in_ship(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_PLAN_LOCK", "0")
    assert plan_always_required() is True
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    ok, reason = require_valid_plan(state)
    assert ok is False
    assert "plan" in reason.lower()


def test_c6_plan_lock_off_only_in_relax(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.setenv("GODKILLER_PLAN_LOCK", "0")
    assert plan_always_required() is False


def test_ship_profile_ignores_dev_relax(monkeypatch: pytest.MonkeyPatch):
    from godkiller_mcp.ship_mode import relax_enabled, ship_mode

    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    assert relax_enabled() is False
    assert ship_mode() is True


def test_critic_hunt_b1_b5_suite_is_loaded():
    """Adversarial surface includes proven B1–B5 (not only self-set C holes)."""
    import importlib

    hunt = importlib.import_module("test_critic_hunt_b1_b5")
    for name in (
        "test_b1_probe_blocks_arbitrary_test_command",
        "test_b2_probe_rejects_absolute_outside_workspace",
        "test_b3_decoy_targets_still_bind_workspace_hash",
        "test_b4_flood_cannot_hide_real_py_from_hash",
        "test_b5_disk_forge_fault_probe_stripped_on_reload",
    ):
        assert hasattr(hunt, name), name
