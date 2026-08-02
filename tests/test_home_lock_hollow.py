"""Regression: hollow native markers + tasks.lock on persist."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.hollow_surface import scan_hollow_surface
from godkiller_mcp.schema import TaskKind


def test_hollow_go_todo_marker(tmp_path: Path) -> None:
    src = tmp_path / "main.go"
    src.write_text('package main\nfunc f() { panic("not implemented") }\n', encoding="utf-8")
    report = scan_hollow_surface([tmp_path])
    assert not report.clean
    assert any(f.kind == "native_placeholder" for f in report.findings)
    assert report.warn  # pure non-Py tree → honesty warn


def test_hollow_rust_todo_macro(tmp_path: Path) -> None:
    src = tmp_path / "lib.rs"
    src.write_text("fn x() { todo!(); }\n", encoding="utf-8")
    report = scan_hollow_surface([tmp_path])
    assert not report.clean
    assert report.warn


def test_task_persist_writes_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GODKILLER_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "goal")
    lock = tmp_path / "tasks" / "tasks.lock"
    assert lock.exists()
    assert (tmp_path / "tasks" / f"{state.handle.task_id}.json").exists()
