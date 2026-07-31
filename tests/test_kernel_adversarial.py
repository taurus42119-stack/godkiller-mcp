"""Adversarial kernel tests — forge / skip / path / allowlist."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from godkiller_mcp.code_intel import check_edit_safe
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.runtime_paths import is_under_package_tree, package_root, resolve_state_root
from godkiller_mcp.schema import EvidenceType, Phase, TaskKind
from godkiller_mcp.verify_bundle import (
    VerifyBundleRunner,
    detect_hacking,
    task_has_passing_verify_bundle,
)


def test_claim_done_rejects_forged_passing_test(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    with pytest.raises(PermissionError, match="server-authored"):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.PASSING_TEST,
            "all green trust me",
            {"source": "verify_bundle", "passed": True},
        )


def test_forged_verify_exit_code_rejected(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    with pytest.raises(PermissionError, match="Forged"):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.EXIT_CODE,
            "fake",
            {"source": "verify_bundle", "passed": True, "exit_code": 0},
        )


def test_server_verify_evidence_counts(tmp_path: Path):
    from godkiller_mcp.freshness import material_hash

    mat = material_hash([], workspace=tmp_path)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.PASSING_TEST,
        "ok",
        {
            "source": "verify_bundle",
            "passed": True,
            "server_authored": True,
            "exit_code": 0,
            "result_digest": "abc123deadbeef",
            "material_hash": mat["material_hash"],
            "material_files": [],
            "cwd": str(tmp_path),
        },
        server_authored=True,
    )
    ok, reason = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok, reason


def test_non_server_payload_does_not_count_even_if_present(tmp_path: Path):
    """Defense in depth if older payloads lack server_authored."""
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    # Inject via server path but strip flag — simulate stale/forged shape
    ev = store.submit_evidence(
        state.handle.task_id,
        EvidenceType.PASSING_TEST,
        "ok",
        {"source": "verify_bundle", "passed": True},
        server_authored=True,
    )
    ev.payload.pop("server_authored", None)
    ok, _ = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok is False


def test_phase_skip_blocked(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    with pytest.raises(ValueError, match="Illegal phase jump"):
        store.assert_phase(state.handle.task_id, Phase.VERIFY)


def test_closed_task_immutable(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    store.mark_closed(state.handle.task_id)
    with pytest.raises(RuntimeError, match="closed"):
        store.submit_evidence(
            state.handle.task_id,
            EvidenceType.LOG,
            "nope",
            {},
        )
    with pytest.raises(RuntimeError, match="closed"):
        store.update_metadata(state.handle.task_id, {"x": 1})
    with pytest.raises(RuntimeError, match="closed"):
        store.assert_phase(state.handle.task_id, Phase.REPRODUCE)


def test_edit_safe_rejects_outside_workspace(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "ok.py").write_text("x=1\n", encoding="utf-8")
    bad = check_edit_safe(["../outside.py"], ws)
    assert bad.payload["safe"] is False
    good = check_edit_safe(["ok.py"], ws)
    assert good.payload["safe"] is True


def test_blast_and_edit_safe_not_client_submittable(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    with pytest.raises(PermissionError):
        store.submit_evidence(state.handle.task_id, EvidenceType.BLAST_RADIUS, "x", {})
    with pytest.raises(PermissionError):
        store.submit_evidence(state.handle.task_id, EvidenceType.EDIT_SAFE, "x", {})


def test_verify_bundle_allowlist():
    blocked, reason = detect_hacking("echo ok")
    assert blocked
    blocked, _ = detect_hacking("rm -rf /")
    assert blocked
    blocked, _ = detect_hacking("pytest -q && echo hi")
    assert blocked
    ok, reason = detect_hacking("python -m pytest -q")
    assert not ok, reason
    ok, reason = detect_hacking("ruff check .")
    assert not ok, reason


def test_verify_runner_blocks_disallowed(tmp_path: Path):
    runner = VerifyBundleRunner(timeout_sec=5)
    result = runner.run(tmp_path, ["echo ok"])
    assert result.passed is False
    assert result.hack_blocked is True


def test_state_not_under_package_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_HOME", str(tmp_path / "home"))
    root = resolve_state_root()
    assert root == (tmp_path / "home").resolve()
    assert not is_under_package_tree(root)
    # package_root itself is under the package tree by definition
    assert is_under_package_tree(package_root() / "src" / "godkiller_mcp")


def test_require_verify_cannot_soft_bypass_without_relax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from godkiller_mcp.policy import PolicyEngine

    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix x")
    # Advance legally through phases with minimal evidence for rubric will still fail
    # Focus: require_verify_bundle=False is ignored
    engine = PolicyEngine()
    allowed, _, reason, gate = engine.request_claim_done(
        state,
        require_verify_bundle=False,
        require_blast_radius=False,
        require_quality_loop=False,
        require_competitor_loop=False,
    )
    assert allowed is False
    assert gate in ("rubric", "phase", "verify", "search", "skill", "hollow", "plan", "fault_probe", "freshness", "tool_propose", "exit", "council", "swarm", "quality")
    assert "verify_bundle" in reason or "Rubric" in reason or "VERIFY" in reason or "search" in reason.lower() or "skill" in reason.lower()
