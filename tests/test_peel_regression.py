"""Regression: peeled handlers must not NameError; slug/path sandbox holds."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.marathon import MarathonRelay, normalize_marathon_slug


@pytest.fixture(autouse=True)
def _seal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "cd" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sample.py").write_text("x = 1\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_ast_grep_no_nameerror_root():
    out = await handle_tool(
        "godkiller_ast_grep", {"pattern": "x = $A", "search_path": "."}
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") != "internal_name_error"
    assert "ROOT" not in str(payload.get("detail") or "")


@pytest.mark.asyncio
async def test_skill_catalog_no_agents_root_nameerror():
    out = await handle_tool("skill_catalog", {"query": "review", "limit": 5})
    payload = json.loads(out[0].text)
    assert payload.get("error") != "internal_name_error"
    assert "AGENTS_ROOT" not in str(payload.get("detail") or "")
    assert "total_indexed" in payload or "skills" in payload


@pytest.mark.asyncio
async def test_pipeline_uses_handle_tool():
    out = await handle_tool(
        "godkiller_pipeline",
        {"steps": [{"tool": "list_modes", "args": {}}], "execute": True},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") != "internal_name_error"
    assert "handle_tool" not in str(payload.get("detail") or "")


@pytest.mark.asyncio
async def test_register_ui_journey_imports():
    # open task first
    opened = json.loads(
        (await handle_tool("open_task", {"kind": "feature", "goal": "ui"}))[0].text
    )
    tid = opened["task_id"]
    out = await handle_tool(
        "register_ui_journey",
        {
            "task_id": tid,
            "name": "smoke",
            "passed": True,
            "steps": [{"action": "click", "target": "#ok"}],
        },
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") != "internal_name_error"
    assert "JourneyStep" not in str(payload.get("detail") or "")


@pytest.mark.asyncio
async def test_retrieve_lessons_export_payload():
    out = await handle_tool(
        "retrieve_lessons",
        {"project_id": "p", "query": "none", "limit": 3},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") != "internal_name_error"
    assert "count" in payload or "lessons" in payload


def test_marathon_slug_rejects_escape(tmp_path: Path):
    with pytest.raises(ValueError):
        normalize_marathon_slug(r"..\escape")
    with pytest.raises(ValueError):
        normalize_marathon_slug("../escape")
    with pytest.raises(ValueError):
        normalize_marathon_slug("a/b")
    relay = MarathonRelay(tmp_path / "m")
    with pytest.raises(ValueError):
        relay.init(slug=r"..\escape", goal="x")
    ok = relay.init(slug="safe-run_1", goal="x")
    assert ok.slug == "safe-run_1"
    assert (tmp_path / "m" / "safe-run_1" / "STATE.json").exists()
    # must not create sibling outside root
    assert not (tmp_path / "escape").exists()


@pytest.mark.asyncio
async def test_read_full_blocks_absolute_outside_workspace(tmp_path: Path):
    outside = Path.home() / "Desktop"
    out = await handle_tool("gk_code_read_full", {"path": str(outside)})
    payload = json.loads(out[0].text)
    assert payload.get("ok") is False
    assert payload.get("error") == "path_outside_workspace"


@pytest.mark.asyncio
async def test_read_full_allows_workspace_file(tmp_path: Path):
    out = await handle_tool("gk_code_read_full", {"path": "sample.py"})
    payload = json.loads(out[0].text)
    assert payload.get("ok") is True
    assert "x = 1" in payload.get("content", "")
