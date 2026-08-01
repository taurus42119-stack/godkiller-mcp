"""### Phase N front-door headings — not bare technical H3s."""

from __future__ import annotations

from godkiller_mcp.phase_heading_gate import (
    evaluate_phase_heading_gate,
    extract_phase_headings,
)
from godkiller_mcp.plan_os import NINE_STEPS, PlanOS


def _steps():
    return {k: f"x {k}" for k in NINE_STEPS}


def test_technical_h3_without_phase_fails_any_domain():
    # SaaS-shaped titles (not games-only)
    saas = """
### Auth Module
### Invoice Ledger
"""
    r = evaluate_phase_heading_gate(text=saas, min_phases=2)
    assert r["ok"] is False
    assert r["technical_headings_without_phase"]

    # Game-shaped titles still fail the same way (regression)
    game = """
### Weapons & Hands System
### World System
"""
    r2 = evaluate_phase_heading_gate(text=game, min_phases=2)
    assert r2["ok"] is False


def test_phase_prefixed_technical_titles_pass():
    md = """
### Phase 1 — Auth Module
### Phase 2 — Invoice Ledger
"""
    r = evaluate_phase_heading_gate(text=md, min_phases=2)
    assert r["ok"] is True
    assert [h["n"] for h in r["phase_headings"]] == [1, 2]


def test_plan_validate_rejects_bare_subsystem_h3():
    pos = PlanOS()
    bad = pos.validate(
        {
            "goal": "accounting SaaS dashboard UI",
            "steps": _steps(),
            "content": """
### Auth Module
build login
### Invoice Ledger
build ledger
""",
        }
    )
    assert bad["valid"] is False
    assert bad["phase_headings"]["ok"] is False

    good = pos.validate(
        {
            "goal": "accounting SaaS dashboard UI",
            "steps": _steps(),
            "phases": [
                {"name": "### Phase 1 — Auth Module"},
                {"name": "### Phase 2 — Invoice Ledger"},
                {"name": "### Phase 3 — Long real playtest / soak"},
                {"name": "### Phase 4 — Capture stepwise screenshots visual_step"},
                {"name": "### Phase 5 — AI inspect visual_critic"},
                {"name": "### Phase 6 — Visual recheck pass"},
            ],
        }
    )
    assert good["phase_headings"]["ok"] is True
    assert good["ui_plan"]["ok"] is True
    assert good["valid"] is True


def test_extract_thai_phase_requires_locale(monkeypatch):
    md = "### เฟส 1 — แกนหลัก\n### เฟส 2 — ทดสอบ"
    monkeypatch.delenv("GODKILLER_LOCALE", raising=False)
    assert extract_phase_headings(md) == []
    monkeypatch.setenv("GODKILLER_LOCALE", "th")
    hs = extract_phase_headings(md)
    assert [h["n"] for h in hs] == [1, 2]
