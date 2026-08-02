"""P1: fault_probe shadow COW + unclean facade gate."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.fault_probe import (
    probe_unclean,
    require_probe_clean_or_restore,
    run_fault_probe,
)


def test_shadow_probe_leaves_original_intact(tmp_path: Path):
    mod = tmp_path / "calc.py"
    original = "def add(a, b):\n    return a + b\n\ndef is_same(a, b):\n    return a == b\n"
    mod.write_text(original, encoding="utf-8")
    (tmp_path / "test_calc.py").write_text(
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
    assert mod.read_text(encoding="utf-8") == original
    assert not probe_unclean(tmp_path)
    assert all(s.get("shadow") is True for s in (report.survivors or [])) or report.clean


def test_require_probe_clean_blocks_when_restore_fails(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(tmp_path))
    gk = tmp_path / ".godkiller"
    gk.mkdir()
    # Unclean with missing bak → restore cannot clear
    (gk / "probe_unclean.json").write_text(
        json.dumps({"files": ["ghost.py"], "bak": "missing"}),
        encoding="utf-8",
    )
    (tmp_path / "ghost.py").write_text("x=1\n", encoding="utf-8")
    blocked = require_probe_clean_or_restore(tmp_path)
    assert blocked is not None
    assert blocked["error"] == "probe_unclean"


@pytest.mark.asyncio
async def test_handle_tool_blocks_on_unclean(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    gk = tmp_path / ".godkiller"
    gk.mkdir()
    (gk / "probe_unclean.json").write_text(
        json.dumps({"files": ["ghost.py"]}),
        encoding="utf-8",
    )
    (tmp_path / "ghost.py").write_text("MUTANT\n", encoding="utf-8")
    out = json.loads(
        (await handle_tool("open_task", {"kind": "feature", "goal": "x"}))[0].text
    )
    assert out.get("error") == "probe_unclean"
    # honesty still allowed
    st = json.loads((await handle_tool("gk_honesty_status", {}))[0].text)
    assert st.get("ok") is True
