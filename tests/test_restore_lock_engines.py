"""P2/P3/P4: restore CLI, seal hint, probe file lock."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.evidence_integrity import load_or_create_seal_key
from godkiller_mcp.fault_probe import probe_unclean, restore_probe_backups, warn_if_probe_unclean
from godkiller_mcp.file_lock import workspace_lock
from godkiller_mcp.restore_cli import main as restore_main


def test_seal_missing_mentions_token_hex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    with pytest.raises(RuntimeError, match="token_hex"):
        load_or_create_seal_key(tmp_path / "tasks")


def test_warn_if_probe_unclean(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    assert warn_if_probe_unclean(tmp_path) is False
    unclean = tmp_path / ".godkiller" / "probe_unclean.json"
    unclean.parent.mkdir(parents=True)
    unclean.write_text("{}", encoding="utf-8")
    assert warn_if_probe_unclean(tmp_path) is True
    err = capsys.readouterr().err
    assert "godkiller-restore" in err
    assert "unclean" in err.lower()


def test_restore_cli_check_and_restore(tmp_path: Path):
    from godkiller_mcp.evidence_store import atomic_write_text

    mod = tmp_path / "calc.py"
    mod.write_text("MUTANT\n", encoding="utf-8")
    backup = tmp_path / ".godkiller" / "probe_backup"
    backup.mkdir(parents=True)
    (backup / "calc.py.bak").write_text("GOOD\n", encoding="utf-8")
    unclean = tmp_path / ".godkiller" / "probe_unclean.json"
    atomic_write_text(unclean, '{"files": ["calc.py"]}')
    assert restore_main(["--workspace", str(tmp_path), "--check"]) == 1
    assert restore_main(["--workspace", str(tmp_path)]) == 0
    assert mod.read_text(encoding="utf-8") == "GOOD\n"
    assert not probe_unclean(tmp_path)


def test_workspace_lock_serializes(tmp_path: Path):
    seen = []
    with workspace_lock(tmp_path, name="probe.lock", timeout_sec=5):
        seen.append(1)
        # nested same-process re-lock would deadlock on Windows LK_NBLCK —
        # only verify lock file exists and unlock works.
        assert (tmp_path / ".godkiller" / "probe.lock").is_file()
    with workspace_lock(tmp_path, name="probe.lock", timeout_sec=5):
        seen.append(2)
    assert seen == [1, 2]


def test_clear_stale_lock_meta_dead_pid(tmp_path: Path):
    from godkiller_mcp.file_lock import _clear_stale_lock, _meta_path

    lock = tmp_path / ".godkiller" / "probe.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("", encoding="utf-8")
    meta = _meta_path(lock)
    meta.write_text('{"pid": 99999999, "ts": 1}', encoding="utf-8")
    assert _clear_stale_lock(lock, max_age_sec=1.0) is True
    assert not meta.exists()


def test_engines_package_exports():
    from godkiller_mcp import engines
    from godkiller_mcp.code_intel import HyperSearchEngine, RepoMapGenerator, SecurityScanEngine

    assert engines.RepoMapGenerator is RepoMapGenerator
    assert engines.HyperSearchEngine is HyperSearchEngine
    assert engines.SecurityScanEngine is SecurityScanEngine
