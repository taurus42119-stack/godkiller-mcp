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
    out = AutoFixEngine().fix(
        str(p),
        pattern="x = 1",
        replacement="x = 2",
        preview_only=False,
        workspace_root=tmp_path,
    )
    assert out.get("preview_only") is False
    assert p.read_text(encoding="utf-8") == "x = 2\n"
    assert out.get("edit_safe", {}).get("safe") is True


def test_autofix_blocks_outside_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    out = AutoFixEngine().fix(
        str(outside),
        pattern="x = 1",
        replacement="x = 2",
        preview_only=False,
        workspace_root=ws,
    )
    assert "error" in out
    assert outside.read_text(encoding="utf-8") == "x = 1\n"


def test_skillify_requires_edit_safe(tmp_path: Path):
    from godkiller_mcp.code_intel import AutoSkillifyEngine

    out = AutoSkillifyEngine().skillify(
        "demo-skill",
        "desc",
        "do the thing",
        workspace_root=str(tmp_path),
    )
    assert out["status"] == "created"
    assert (tmp_path / ".agents" / "skills" / "demo-skill" / "SKILL.md").is_file()
    assert out.get("edit_safe", {}).get("safe") is True
