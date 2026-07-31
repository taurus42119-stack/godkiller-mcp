"""Freshness bind + host prove + deeper fault probe."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.fault_probe import run_fault_probe
from godkiller_mcp.freshness import evidence_fresh_against_disk, material_hash
from godkiller_mcp.prove import prove
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.verify_bundle import task_has_passing_verify_bundle


def test_material_hash_stable_and_changes_on_edit(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\n", encoding="utf-8")
    h1 = material_hash([f], workspace=tmp_path)
    h2 = material_hash([f], workspace=tmp_path)
    assert h1["material_hash"] == h2["material_hash"]
    f.write_text("x = 2\n", encoding="utf-8")
    h3 = material_hash([f], workspace=tmp_path)
    assert h3["material_hash"] != h1["material_hash"]


def test_stale_verify_rejected_after_edit(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_FRESHNESS", "1")
    f = tmp_path / "m.py"
    f.write_text("def f():\n    return 1\n", encoding="utf-8")
    mat = material_hash([f], workspace=tmp_path)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "g")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.EDIT_SAFE,
        "e",
        {"path": str(f), "server_authored": True},
        server_authored=True,
    )
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.PASSING_TEST,
        "ok",
        {
            "source": "verify_bundle",
            "passed": True,
            "server_authored": True,
            "result_digest": "d" * 64,
            "material_hash": mat["material_hash"],
            "material_files": mat["files"],
            "cwd": str(tmp_path),
        },
        server_authored=True,
    )
    ok1, _ = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok1 is True
    f.write_text("def f():\n    return 2\n", encoding="utf-8")
    ok2, reason = task_has_passing_verify_bundle(store.get(state.handle.task_id))
    assert ok2 is False
    assert "stale" in reason.lower() or "material_hash" in reason.lower()


def test_prove_fails_closed_on_red_tests(tmp_path: Path):
    (tmp_path / "test_x.py").write_text("def test_x():\n    assert False\n", encoding="utf-8")
    r = prove(tmp_path, targets=[], test_command="python -m pytest -q --tb=no", fail_on_survivors=False, fail_on_hollow=False)
    assert r["ok"] is False
    assert r["verdict"] == "NOT_PROVED"


def test_prove_and_probe_on_strong_suite(tmp_path: Path):
    (tmp_path / "calc.py").write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (tmp_path / "test_calc.py").write_text(
        "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    r = prove(
        tmp_path,
        targets=["calc.py"],
        test_command="python -m pytest -q --tb=no",
        fail_on_survivors=True,
        fail_on_hollow=True,
    )
    assert r["gates"]["verify_bundle"]["passed"] is True
    assert r["gates"]["fault_probe"]["clean"] is True
    assert r["ok"] is True


def test_diff_scoped_probe_explicit_targets(tmp_path: Path):
    mod = tmp_path / "calc.py"
    mod.write_text(
        "def add(a, b):\n    return a + b\n\ndef is_same(a, b):\n    return a == b\n",
        encoding="utf-8",
    )
    (tmp_path / "test_calc.py").write_text(
        "from calc import add, is_same\n"
        "def test_add():\n    assert add(2, 3) == 5\n"
        "def test_same():\n    assert is_same(1, 1) and not is_same(1, 2)\n",
        encoding="utf-8",
    )
    report = run_fault_probe(
        workspace=tmp_path,
        targets=[mod],
        test_command="python -m pytest -q --tb=no",
        max_mutants=6,
    )
    assert report.scope == "explicit_targets"
    assert report.mutants_tried >= 1
    assert report.clean is True
    assert report.material_hash
