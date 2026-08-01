"""Fault probe backup / unclean marker + theatre tags."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.fault_probe import probe_unclean, restore_probe_backups, run_fault_probe
from godkiller_mcp.quality_gates import build_compare_delta, build_competitor_scan
from godkiller_mcp.ship_mode import profile_label


def test_profile_label_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    assert profile_label() == "default"


def test_competitor_scan_not_claim_armor():
    r = build_competitor_scan(
        ["q"],
        [
            {"name": "A", "url": "https://example.com/a"},
            {"name": "B", "url": "https://example.com/b"},
        ],
    )
    p = r.to_payload()
    assert p["ceremony_complete"] is True
    assert p["passed"] is True
    assert p["claim_armor"] is False
    assert p["agent_supplied"] is True
    assert p["attested"] is False


def test_compare_delta_not_claim_armor():
    r = build_compare_delta({"ux": 1.0}, still_losing=False, best_competitor="Fake")
    p = r.to_payload()
    assert p["passed"] is True
    assert p["claim_armor"] is False
    assert p["agent_supplied"] is True


def test_fault_probe_leaves_original_and_clears_unclean(tmp_path: Path):
    mod = tmp_path / "calc.py"
    original = "def add(a, b):\n    return a + b\n"
    mod.write_text(original, encoding="utf-8")
    test = tmp_path / "test_calc.py"
    test.write_text(
        "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = run_fault_probe(
        workspace=tmp_path,
        target_file=mod,
        test_command="python -m pytest -q --tb=no",
        timeout_sec=30,
    )
    assert report.mutants_tried >= 1
    assert mod.read_text(encoding="utf-8") == original
    assert not probe_unclean(tmp_path)


def test_restore_probe_backups_from_unclean(tmp_path: Path):
    from godkiller_mcp.evidence_store import atomic_write_text

    mod = tmp_path / "calc.py"
    mod.write_text("GOOD\n", encoding="utf-8")
    backup = tmp_path / ".godkiller" / "probe_backup"
    backup.mkdir(parents=True)
    (backup / "calc.py.bak").write_text("GOOD\n", encoding="utf-8")
    # Simulate crash: mutant left on disk + unclean marker
    mod.write_text("MUTANT\n", encoding="utf-8")
    unclean = tmp_path / ".godkiller" / "probe_unclean.json"
    atomic_write_text(
        unclean,
        '{"files": ["calc.py"], "bak": "x"}',
    )
    assert probe_unclean(tmp_path)
    info = restore_probe_backups(tmp_path)
    assert "calc.py" in info["restored"]
    assert mod.read_text(encoding="utf-8") == "GOOD\n"
    assert not probe_unclean(tmp_path)
