"""Hollow surface + session ledger + verify digest gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.hollow_surface import claim_hollow_gate, scan_hollow_surface
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.session_ledger import append_ledger, verify_ledger
from godkiller_mcp.verify_bundle import (
    VerifyBundleRunner,
    task_has_passing_verify_bundle,
)


def test_hollow_surface_flags_pass_and_todo(tmp_path: Path):
    f = tmp_path / "mod.py"
    f.write_text(
        "def work():\n    pass\n\ndef other():\n    return 1  # TODO finish\n",
        encoding="utf-8",
    )
    report = scan_hollow_surface([tmp_path])
    kinds = {x.kind for x in report.findings}
    assert "hollow_body" in kinds
    assert "marker" in kinds
    assert report.clean is False


def test_hollow_surface_clean_real_body(tmp_path: Path):
    f = tmp_path / "ok.py"
    f.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    report = scan_hollow_surface([tmp_path])
    assert report.clean


def test_claim_hollow_gate_blocks_touched_hollow(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text("def x():\n    raise NotImplementedError()\n", encoding="utf-8")
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "g")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.EDIT_SAFE,
        "edit",
        {"path": str(bad), "server_authored": True},
        server_authored=True,
    )
    ok, reason, _ = claim_hollow_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "hollow_surface" in reason


def test_verify_bundle_binds_result_digest(tmp_path: Path):
    (tmp_path / "test_ok.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    result = VerifyBundleRunner(timeout_sec=30).run(tmp_path, ["python -m pytest -q"])
    assert result.passed
    payload = result.to_payload()
    assert payload["result_digest"]
    assert len(payload["result_digest"]) == 64


def test_passing_verify_requires_digest(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "g")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.PASSING_TEST,
        "ok",
        {
            "source": "verify_bundle",
            "passed": True,
            "server_authored": True,
            "exit_code": 0,
        },
        server_authored=True,
    )
    ok, reason = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok is False
    assert "result_digest" in reason


def test_session_ledger_hash_chain(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("GODKILLER_HOME", str(tmp_path / "home"))
    a = append_ledger("open", {"n": 1}, task_id="t1", state_root=tmp_path / "home")
    b = append_ledger("verify_bundle", {"n": 2}, task_id="t1", state_root=tmp_path / "home")
    assert a["digest"] == b["prev"]
    assert verify_ledger(tmp_path / "home")["ok"] is True
