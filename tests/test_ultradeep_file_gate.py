from __future__ import annotations

from godkiller_mcp import ultradeep_engine as ude
from godkiller_mcp.server import FACADE_ACTIONS


def test_per_file_think_plan_edit_blocks_batch():
    gate = ude.empty_file_gate(enabled=True)
    ude.queue_files(gate, ["src/a.py", "src/b.py"])
    ok, reason = ude.check_edit_paths(gate, ["src/a.py", "src/b.py"])
    assert ok is False
    assert "at most" in reason.lower() or "batch" in reason.lower() or "1 file" in reason.lower()


def test_per_file_requires_think_then_plan():
    gate = ude.empty_file_gate(enabled=True)
    ude.queue_files(gate, ["src/a.py"])
    ok, _ = ude.check_edit_paths(gate, ["src/a.py"])
    assert ok is False

    bad = ude.record_think(gate, "src/a.py", "short", hypotheses=["h1", "h2", "h3"])
    assert bad["ok"] is False

    think = "x" * 130
    hyps = ["path A fails", "path B race", "path C wrong assumption"]
    r1 = ude.record_think(gate, "src/a.py", think, hypotheses=hyps, tools_used=["gk_code.search"])
    assert r1["ok"] is True
    ok, _ = ude.check_edit_paths(gate, ["src/a.py"])
    assert ok is False  # still need plan

    r2 = ude.record_plan(gate, "src/a.py", "Change guard clause; add test for zero divisor. " + ("y" * 40))
    assert r2["ok"] is True
    ok, reason = ude.check_edit_paths(gate, ["src/a.py"])
    assert ok is True, reason

    # wrong file blocked
    ok2, _ = ude.check_edit_paths(gate, ["src/b.py"])
    assert ok2 is False

    ude.advance_file(gate, "src/a.py")
    assert gate["files"]["src/a.py"]["stage"] == "done"


def test_facade_exposes_ultradeep_actions():
    assert "ultradeep_think" in FACADE_ACTIONS["gk_mode"]
    assert "ultradeep_plan" in FACADE_ACTIONS["gk_mode"]
    assert "ultradeep_queue" in FACADE_ACTIONS["gk_mode"]


def test_gate_disabled_allows_legacy():
    gate = ude.empty_file_gate(enabled=False)
    ok, _ = ude.check_edit_paths(gate, ["a.py", "b.py", "c.py"])
    assert ok is True
