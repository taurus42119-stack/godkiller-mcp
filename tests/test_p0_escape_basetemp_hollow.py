"""P0: screenshot escape, pytest --basetemp, hollow roots outside workspace."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from godkiller_mcp.browser_runtime import PlaywrightBrowser
from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.path_sandbox import normalize_artifact_name
from godkiller_mcp.verify_bundle import detect_hacking


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "cd" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)


def test_pytest_deny_basetemp():
    blocked, reason = detect_hacking("python -m pytest -q --basetemp=/tmp/escape")
    assert blocked
    assert "basetemp" in reason.lower() or "deny" in reason.lower()
    blocked2, _ = detect_hacking("pytest --basetemp=C:/Temp/out")
    assert blocked2


def test_screenshot_name_escape_blocked(tmp_path: Path):
    browser = PlaywrightBrowser(artifact_dir=tmp_path / "arts")
    browser._page = MagicMock()
    out = browser.screenshot(r"..\..\escape.png")
    assert out.get("ok") is False
    assert out.get("error") in ("invalid_artifact_name", "path_outside_workspace")
    assert not (tmp_path.parent / "escape.png").exists()
    assert not (Path.cwd().parent / "escape.png").exists()


def test_screenshot_safe_name_ok(tmp_path: Path):
    browser = PlaywrightBrowser(artifact_dir=tmp_path / "arts")
    browser._page = MagicMock()
    out = browser.screenshot("shot.png")
    assert out.get("ok") is True
    path = Path(out["path"])
    assert path.parent.resolve() == (tmp_path / "arts").resolve()
    browser._page.screenshot.assert_called_once()


def test_normalize_rejects_dotdot():
    with pytest.raises(ValueError):
        normalize_artifact_name("../x.png")


@pytest.mark.asyncio
async def test_hollow_surface_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "hollow_escape_dir"
    outside.mkdir(exist_ok=True)
    (outside / "hollow.py").write_text("TODO: pass\n", encoding="utf-8")
    out = await handle_tool("hollow_surface", {"paths": [str(outside)]})
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"


@pytest.mark.asyncio
async def test_verify_bundle_blocks_outside_workspace(tmp_path: Path):
    outside = tmp_path.parent / "verify_escape_ws"
    outside.mkdir(exist_ok=True)
    out = await handle_tool(
        "verify_bundle",
        {"workspace": str(outside), "commands": ["python -m pytest -q"]},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"
