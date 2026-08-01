"""VIEW propose-study when confidence < 99%."""

from __future__ import annotations

from godkiller_mcp.view_propose import (
    CONFIDENCE_PROPOSE_BELOW,
    build_view_study_proposal,
    should_propose_view,
)


def test_threshold_99():
    assert CONFIDENCE_PROPOSE_BELOW == 99.0
    assert should_propose_view(0) is True
    assert should_propose_view(98.9) is True
    assert should_propose_view(99.0) is False
    assert should_propose_view(None) is True


def test_proposal_shape():
    p = build_view_study_proposal(
        goal="build FPS",
        confidence_pct=70,
        topics=["three.js pointer lock"],
        known_gaps=["weapon recoil math"],
    )
    assert p["propose_now"] is True
    assert "chat_template" in p
    assert p["steps"]
    assert "view_propose_study" in str(p["next_tools"])
