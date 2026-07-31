"""Self-heal structure + visual pixel-first gates."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from godkiller_mcp.code_intel import SelfHealingEngine
from godkiller_mcp.quality_gates import CriticVerdict, run_visual_critic


def test_visual_checklist_alone_cannot_green():
    r = run_visual_critic(
        kind="feature",
        description="beautiful polished production UI",
        checklist={
            "first_screen_readable": True,
            "not_placeholder": True,
            "materials_or_hierarchy_ok": True,
            "reference_delta_acceptable": True,
        },
        agent_verdict="GREEN",
    )
    assert r.verdict == CriticVerdict.RED
    assert any("pixels_required" in f for f in r.findings)


def test_visual_green_needs_real_nonblank_pixels(tmp_path: Path):
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow missing")
    path = tmp_path / "ui.png"
    img = Image.new("RGB", (240, 240))
    px = img.load()
    for y in range(240):
        for x in range(240):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
    img.save(path)
    r = run_visual_critic(
        kind="feature",
        description="screen",
        checklist={
            "materials_or_hierarchy_ok": True,
            "reference_delta_acceptable": True,
        },
        screenshot_path=str(path),
    )
    assert r.checklist.get("pixels_verified") is True
    assert r.verdict == CriticVerdict.GREEN
    assert r.to_payload().get("vision", {}).get("passed") is True


def test_self_heal_uses_traceback_structure_not_substring_only():
    tb = (
        'Traceback (most recent call last):\n'
        '  File "/tmp/app.py", line 10, in main\n'
        '    boom()\n'
        'ValueError: bad\n'
    )
    plan = SelfHealingEngine().diagnose("other_tool", tb)
    assert plan["method"] == "traceback_parse"
    assert plan["recommended_tool"] == "godkiller_log_trace"
    assert plan["signals"]["exception_type"] == "ValueError"
    assert "frames" in plan


def test_self_heal_tool_map_not_no_matches_substring():
    plan = SelfHealingEngine().diagnose(
        "godkiller_hyper_search",
        "completely unrelated failure text",
        {"pattern": "def $FUNC()", "search_path": "."},
    )
    assert plan["method"] == "tool_fallback_map"
    assert plan["recommended_tool"] == "godkiller_ast_grep"


def test_self_heal_executes_and_marks_verified():
    async def _run():
        class TC:
            def __init__(self, text):
                self.text = text

        async def executor(name, args):
            assert name == "godkiller_log_trace"
            return [TC('{"exception_type": "ValueError", "frame_count": 1}')]

        res = await SelfHealingEngine().heal_and_run(
            "other",
            "Traceback...\nValueError: boom",
            executor=executor,
        )
        assert res["executed"] is True
        assert res.get("heal_verified") is True

    asyncio.run(_run())
