"""P0: workspace sandbox for reads/writes beyond read_full."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.dispatch import handle_tool, handoff
from godkiller_mcp.handoff_docs import SpecFeedbackStore
from godkiller_mcp.path_sandbox import normalize_slug


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ef" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in_ws.py").write_text("secret_in = 1\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_exhaustive_blocks_outside_workspace(tmp_path: Path):
    outside = tmp_path.parent / "gk_out_exh"
    outside.mkdir(exist_ok=True)
    (outside / "TOPSECRET.txt").write_text("TOPSECRET\n", encoding="utf-8")
    out = await handle_tool(
        "godkiller_exhaustive_read", {"dir_path": str(outside), "max_files": 5}
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"
    assert "TOPSECRET" not in json.dumps(payload)


@pytest.mark.asyncio
async def test_hyper_search_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "gk_out_search"
    outside.mkdir(exist_ok=True)
    (outside / "TOPSECRET.txt").write_text("TOPSECRET\n", encoding="utf-8")
    out = await handle_tool(
        "godkiller_hyper_search",
        {"pattern": "TOPSECRET", "search_path": str(outside)},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"


@pytest.mark.asyncio
async def test_context_preview_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "gk_out_prev.txt"
    outside.write_text("TOPSECRET\n", encoding="utf-8")
    out = await handle_tool(
        "godkiller_context_preview", {"file_path": str(outside)}
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"


def test_handoff_slug_escape_blocked(tmp_path: Path):
    store = SpecFeedbackStore(tmp_path / "handoff")
    with pytest.raises(ValueError):
        store.write_feedback(r"..\..\FBESC", "x", score=1, passed=True)
    with pytest.raises(ValueError):
        normalize_slug(r"..\esc")
    assert not (Path.home() / "FBESC_feedback.json").exists()
    ok = store.write_feedback("safe_slug", "ok", score=1, passed=True)
    assert ok["slug"] == "safe_slug"
    assert (tmp_path / "handoff" / "safe_slug_feedback.json").exists()


@pytest.mark.asyncio
async def test_capture_shot_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "shot_out.txt"
    outside.write_text("x", encoding="utf-8")
    opened = json.loads(
        (await handle_tool("open_task", {"kind": "feature", "goal": "shot"}))[0].text
    )
    out = await handle_tool(
        "capture_shot",
        {"task_id": opened["task_id"], "path": str(outside)},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"


@pytest.mark.asyncio
async def test_inspect_image_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "img_out.txt"
    outside.write_text("x", encoding="utf-8")
    out = await handle_tool("godkiller_inspect_image", {"path": str(outside)})
    payload = json.loads(out[0].text)
    assert payload.get("error") == "path_outside_workspace"


@pytest.mark.asyncio
async def test_write_feedback_tool_blocks_escape():
    out = await handle_tool(
        "write_feedback",
        {"slug": r"..\..\FBESC2", "content": "x", "score": 1, "passed": True},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") in ("invalid_value", "path_outside_workspace") or "illegal" in str(
        payload.get("detail") or ""
    )
    assert not (Path.home() / "FBESC2_feedback.json").exists()
