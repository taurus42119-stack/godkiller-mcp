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
    monkeypatch.delenv("GODKILLER_WORKSPACE", raising=False)
    monkeypatch.delenv("GODKILLER_HOME", raising=False)
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
async def test_default_dot_searches_cwd_not_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """P0: '.' must resolve to IDE cwd/workspace, never installed package ROOT."""
    from godkiller_mcp.runtime_paths import package_root

    marker = "MARKER_ONLY_IN_USER_WS_XYZ"
    (tmp_path / "user_ws_marker.py").write_text(f"{marker} = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert Path.cwd().resolve() == tmp_path.resolve()
    assert package_root().resolve() != tmp_path.resolve()

    out = await handle_tool(
        "godkiller_hyper_search",
        {"pattern": marker, "search_path": ".", "max_results": 20},
    )
    payload = json.loads(out[0].text)
    assert payload.get("error") != "path_outside_workspace", payload
    blob = json.dumps(payload)
    assert marker in blob
    # Must not pretend the package tree was the workspace
    pkg = str(package_root().resolve()).replace("\\", "/").lower()
    matches = payload.get("matches") or []
    for m in matches:
        f = str((m.get("file") if isinstance(m, dict) else m) or "").replace("\\", "/").lower()
        if f:
            assert pkg not in f or str(tmp_path.resolve()).replace("\\", "/").lower() in f


@pytest.mark.asyncio
async def test_default_dot_repo_map_uses_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from godkiller_mcp.runtime_paths import package_root

    (tmp_path / "only_in_user_ws.py").write_text("def only_in_user_ws():\n    return 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out = await handle_tool("godkiller_repo_map", {"workspace_root": ".", "max_tokens": 500})
    text = out[0].text
    assert "only_in_user_ws" in text
    assert str(package_root().resolve()) not in text or "only_in_user_ws" in text


@pytest.mark.asyncio
async def test_visual_step_blocks_outside(tmp_path: Path):
    outside = tmp_path.parent / "gk_visual_escape.png"
    outside.write_bytes(b"\x89PNG\r\n\x1a\n")
    opened = json.loads(
        (await handle_tool("open_task", {"kind": "feature", "goal": "viz"}))[0].text
    )
    out = await handle_tool(
        "visual_step",
        {
            "task_id": opened["task_id"],
            "path": str(outside),
            "step_id": "01_boot",
            "expected_elements": ["OK"],
        },
    )
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
