"""UI-mandatory phases in plan_validate."""

from __future__ import annotations

from godkiller_mcp.plan_os import NINE_STEPS, PlanOS
from godkiller_mcp.ui_plan_phases import detect_ui_plan_work, evaluate_ui_plan_phases


def _full_steps(**overrides):
    steps = {k: f"content for {k}" for k in NINE_STEPS}
    steps.update(overrides)
    return steps


def test_non_ui_plan_still_valid_without_playtest_phases():
    pos = PlanOS()
    r = pos.validate(
        {
            "goal": "fix CLI parser bug",
            "steps": _full_steps(),
            "phases": [
                {"name": "### Phase 1 — Reproduce"},
                {"name": "### Phase 2 — Fix + verify"},
            ],
        }
    )
    assert r["valid"] is True
    assert r["ui_plan"]["ui_work"] is False


def test_ui_plan_without_phases_invalid():
    pos = PlanOS()
    r = pos.validate(
        {
            "goal": "Ship a Three.js FPS game UI",
            "steps": _full_steps(**{"8_test_plan": "pytest only"}),
            "phases": [
                {"name": "### Phase 1 — Mesh"},
                {"name": "### Phase 2 — Controls"},
            ],
        }
    )
    assert r["valid"] is False
    assert r["ui_plan"]["ui_work"] is True
    assert "playtest" in r["ui_plan"]["missing_intents"]
    assert r["allowed_to_edit"] is False


def test_ui_keywords_only_in_test_plan_not_enough():
    """Regression: backend intents in 8_test_plan without ### Phase N UI titles."""
    pos = PlanOS()
    r = pos.validate(
        {
            "goal": "Build web dashboard UI",
            "steps": _full_steps(
                **{
                    "8_test_plan": (
                        "playtest soak; capture visual_step; "
                        "visual_critic inspect; recheck"
                    )
                }
            ),
            "phases": [
                {"name": "### Phase 1 — Layout"},
                {"name": "### Phase 2 — Charts"},
            ],
        }
    )
    assert r["phase_headings"]["ok"] is True
    assert r["ui_plan"]["ok"] is False
    assert r["valid"] is False


def test_ui_plan_with_four_phases_valid():
    pos = PlanOS()
    r = pos.validate(
        {
            "goal": "Build web dashboard UI",
            "steps": _full_steps(
                **{
                    "8_test_plan": (
                        "playtest soak long; capture screenshots visual_step; "
                        "visual_critic inspect; recheck visual pass"
                    )
                }
            ),
            "phases": [
                {"name": "### Phase 5 — Long real playtest / soak", "dod": "เล่นจริงยาวๆ"},
                {"name": "### Phase 6 — Capture stepwise screenshots", "dod": "visual_step"},
                {"name": "### Phase 7 — AI inspect captures visual_critic", "dod": "อ่านรูป"},
                {"name": "### Phase 8 — Visual recheck pass เช็คอีกรอบ", "dod": "second pass"},
            ],
        }
    )
    assert r["ui_plan"]["missing_intents"] == []
    assert r["valid"] is True
    assert r["ui_plan"]["ui_work"] is True


def test_api_surface_skips_ui_gate():
    assert detect_ui_plan_work(goal="REST API only", metadata={"surface": "api"}) is False
    r = evaluate_ui_plan_phases(goal="game UI", metadata={"surface": "api"})
    assert r["ok"] is True
    assert r["ui_work"] is False


def test_template_seeds_ui_test_plan():
    t = PlanOS().template("make a react dashboard")
    assert t["ui_work_detected"] is True
    assert "visual_step" in t["steps"]["8_test_plan"]
    assert "ui_phases_markdown" in t


def test_markdown_phases_parsed_for_ui_gate():
    md = """
# Goal: Ship browser game UI
## 1 Goal
ship it
## 2 Constraints
none
## 3 Stakeholders
user
## 4 Current State
empty
## 5 Options
a
## 6 Chosen Design
three.js
## 7 Blast Radius
index.html
## 8 Test Plan
unit + playtest
## 9 Rollout Verify
ship

### Phase 1 — Build mesh
### Phase 2 — Long real playtest soak เล่นจริง
### Phase 3 — Capture screenshots visual_step
### Phase 4 — AI inspect visual_critic อ่านรูป
### Phase 5 — Recheck เช็คอีกรอบ
"""
    # Fill nine steps via markdown loader — titles must match NINE_STEPS matching
    pos = PlanOS()
    # Use dict with markdown extra + phases from load
    spec = pos.load_plan(md)
    # load_plan may not fill all 9 from ## titles depending on matching — seed steps
    for k in NINE_STEPS:
        if not (spec.steps.get(k) or "").strip():
            spec.steps[k] = "filled"
    spec.steps["8_test_plan"] = "playtest capture visual_critic recheck"
    r = pos.validate(spec)
    assert r["ui_plan"]["ui_work"] is True
    assert r["valid"] is True
