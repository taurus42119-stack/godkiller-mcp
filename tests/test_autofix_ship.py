"""AutoFix ship forces preview_only."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.code_intel import AutoFixEngine


def test_autofix_ship_forces_preview(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    p = tmp_path / "a.py"
    p.write_text("x = 1\n", encoding="utf-8")
    out = AutoFixEngine().fix(str(p), pattern="x = 1", replacement="x = 2", preview_only=False)
    assert out.get("preview_only") is True
    assert out.get("forced_preview") is True
    assert p.read_text(encoding="utf-8") == "x = 1\n"


def test_autofix_relax_can_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    p = tmp_path / "a.py"
    p.write_text("x = 1\n", encoding="utf-8")
    out = AutoFixEngine().fix(str(p), pattern="x = 1", replacement="x = 2", preview_only=False)
    assert out.get("preview_only") is False
    assert p.read_text(encoding="utf-8") == "x = 2\n"
