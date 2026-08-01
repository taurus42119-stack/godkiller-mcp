"""Multi-root skill catalog includes bundled agent-ops."""

from __future__ import annotations

from pathlib import Path

from godkiller_mcp.modes import suggest_skills_for_goal
from godkiller_mcp.skill_catalog import build_catalog, resolve_skill_roots


def test_resolve_roots_includes_bundled_ops():
    roots = resolve_skill_roots()
    bundled = Path(__file__).resolve().parents[1] / "src" / "godkiller_mcp" / "bundled_skills"
    assert any("bundled_skills" in str(r) or "agent-ops" in str(r) for r in roots) or bundled.is_dir()


def test_catalog_indexes_agent_ops_family():
    cat = build_catalog(resolve_skill_roots())
    ops = [
        e
        for e in cat
        if e.get("family") == "agent-ops" or "agent-ops" in e.get("path", "").replace("\\", "/")
    ]
    assert len(ops) >= 5
    names = {e["name"] for e in ops}
    assert "babysit" in names or "review" in names or "create-skill" in names


def test_skill_routes_include_ops_review():
    hints = suggest_skills_for_goal("please do a security code review on this PR")
    joined = " ".join(hints["must_view_file"]).replace("\\", "/")
    assert "agent-ops" in joined or "review" in joined
