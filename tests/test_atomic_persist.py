"""Slice A: EvidenceStore._persist uses atomic replace."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from godkiller_mcp.evidence_store import EvidenceStore, atomic_write_text
from godkiller_mcp.schema import TaskKind


def test_atomic_write_text_roundtrip(tmp_path: Path):
    path = tmp_path / "t.json"
    atomic_write_text(path, '{"ok":true}')
    assert path.read_text(encoding="utf-8") == '{"ok":true}'
    atomic_write_text(path, '{"ok":false}')
    assert path.read_text(encoding="utf-8") == '{"ok":false}'


def test_atomic_write_preserves_prior_on_midwrite_failure(tmp_path: Path):
    path = tmp_path / "task.json"
    atomic_write_text(path, '{"v":1}')

    real_replace = __import__("os").replace

    def boom(src, dst):
        raise OSError("simulated crash before replace")

    with mock.patch("os.replace", side_effect=boom):
        with pytest.raises(OSError, match="simulated crash"):
            atomic_write_text(path, '{"v":2}')

    assert path.read_text(encoding="utf-8") == '{"v":1}'
    leftovers = list(tmp_path.glob(".task.json.*.tmp"))
    assert leftovers == [] or all(not p.exists() for p in leftovers)
    # prior file untouched; replace never ran
    assert real_replace  # silence lint


def test_evidence_store_persist_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(kind=TaskKind.BUGFIX, goal="atomic")
    path = tmp_path / "tasks" / f"{state.handle.task_id}.json"
    assert path.exists()
    body = path.read_text(encoding="utf-8")
    assert state.handle.task_id in body
    assert '"goal": "atomic"' in body or '"goal":"atomic"' in body.replace(" ", "")
