"""P0: workspace pin — refuse unpinned $HOME as MCP sandbox."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.path_sandbox import (
    WorkspaceRootError,
    ensure_under_root,
    path_gate_error,
    workspace_root,
    workspace_status,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ef" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_WORKSPACE", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_HOME_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)


def test_workspace_root_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pinned = tmp_path / "proj"
    pinned.mkdir()
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(pinned))
    monkeypatch.chdir(tmp_path)
    assert workspace_root() == pinned.resolve()
    st = workspace_status()
    assert st["ok"] is True
    assert st["pinned"] is True
    assert st["root"] == str(pinned.resolve())


def test_workspace_root_rejects_home_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home.resolve()))
    monkeypatch.chdir(home)
    with pytest.raises(WorkspaceRootError, match="workspace_root_unpinned"):
        workspace_root()
    st = workspace_status()
    assert st["ok"] is False
    assert st["error"] == "workspace_root_unpinned"


def test_workspace_root_allow_home_escape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "fake_home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home.resolve()))
    monkeypatch.chdir(home)
    monkeypatch.setenv("GODKILLER_ALLOW_HOME_WORKSPACE", "1")
    assert workspace_root() == home.resolve()


@pytest.mark.asyncio
async def test_read_full_blocks_outside_when_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "ok.py").write_text("x=1\n", encoding="utf-8")
    outside = tmp_path / "secret.env"
    outside.write_text("SECRET=1\n", encoding="utf-8")
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(ws))
    monkeypatch.chdir(tmp_path)  # cwd outside pin — pin must win

    ok = json.loads(
        (await handle_tool("gk_code_read_full", {"path": str(ws / "ok.py")}))[0].text
    )
    assert ok.get("ok") is True
    assert "x=1" in ok.get("content", "")

    bad = json.loads(
        (await handle_tool("gk_code_read_full", {"path": str(outside)}))[0].text
    )
    assert bad.get("error") == "path_outside_workspace"
    assert "SECRET" not in json.dumps(bad)


@pytest.mark.asyncio
async def test_read_full_home_file_blocked_when_project_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression: .gitconfig under $HOME must not be readable via MCP."""
    home = tmp_path / "home"
    home.mkdir()
    gitconfig = home / ".gitconfig"
    gitconfig.write_text("[user]\n\tname = LeakMe\n", encoding="utf-8")
    ws = tmp_path / "project"
    ws.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(ws))
    monkeypatch.chdir(ws)

    out = json.loads(
        (await handle_tool("gk_code_read_full", {"path": str(gitconfig)}))[0].text
    )
    assert out.get("error") == "path_outside_workspace"
    assert "LeakMe" not in json.dumps(out)


def test_path_gate_reports_unpinned_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "a.py").write_text("1\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home.resolve()))
    monkeypatch.chdir(home)
    err = path_gate_error(str(home / "a.py"))
    assert err is not None
    assert err["error"] == "workspace_root_unpinned"


def test_ensure_under_root_explicit_still_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "in.py"
    f.write_text("ok\n", encoding="utf-8")
    # explicit may only confirm authorized root
    assert ensure_under_root(f, tmp_path) == f.resolve()


def test_path_gate_refuses_attacker_root_rebind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """P1: path_gate_error(..., root=$HOME) must NOT widen the jail."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "secret.py").write_text("LEAK\n", encoding="utf-8")
    ws = tmp_path / "project"
    ws.mkdir()
    (ws / "ok.py").write_text("1\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home.resolve()))
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(ws))
    monkeypatch.chdir(ws)

    err = path_gate_error(str(home / "secret.py"), root=home)
    assert err is not None
    assert err["error"] == "workspace_root_rebinding_refused"

    # Without rebind, secret under $HOME is outside project
    err2 = path_gate_error(str(home / "secret.py"))
    assert err2 is not None
    assert err2["error"] == "path_outside_workspace"
