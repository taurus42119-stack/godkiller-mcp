"""P0: gk_scan.semgrep must honor workspace path gate (no outside snippets)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.scan_runtime import run_semgrep


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    monkeypatch.delenv("GODKILLER_WORKSPACE", raising=False)
    monkeypatch.delenv("GODKILLER_HOME", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")


def test_run_semgrep_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "semgrep_escape"
    outside.mkdir(exist_ok=True)
    secret = outside / "leak.py"
    secret.write_text('PASSWORD = "supersecret"\n', encoding="utf-8")
    out = run_semgrep(str(outside))
    assert out.get("error") == "path_outside_workspace"
    blob = json.dumps(out)
    assert "supersecret" not in blob
    assert "PASSWORD" not in blob


@pytest.mark.asyncio
async def test_gk_scan_semgrep_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "semgrep_escape2"
    outside.mkdir(exist_ok=True)
    (outside / "leak.py").write_text('PASSWORD = "supersecret2"\n', encoding="utf-8")
    out = json.loads(
        (await handle_tool("gk_scan_semgrep", {"target_path": str(outside)}))[0].text
    )
    assert out.get("error") == "path_outside_workspace"
    assert "supersecret2" not in json.dumps(out)
