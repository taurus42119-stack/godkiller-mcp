"""Smoke tests for Antigravity A/B helpers."""

from __future__ import annotations

from benchmarks.score_11 import DIMENSIONS, score_dimensions


def test_eleven_dimensions_defined():
    assert len(DIMENSIONS) == 11


def test_header_only_zeroes_overall():
    oracle = {
        "counts": {"passed": 10, "failed": 0, "skipped": 0, "collected": 10},
        "has_body": False,
        "header_only": True,
    }
    delta = {"pct": 100.0, "changed_files": 6, "total_files": 6, "details": []}
    signals = {k: True for k in (
        "exhaustive_read", "open_task", "plan_os", "blast_radius", "edit_safe",
        "verify_bundle", "claim_done", "council", "security", "visual_critic",
        "screenshot_count", "marathon", "hay_chars",
    )}
    dims, meta = score_dimensions(oracle, delta, signals)
    assert meta["overall_score"] == 0.0
    assert dims["3_output_integrity"] == 0.0


def test_full_body_can_score():
    oracle = {
        "counts": {"passed": 516, "failed": 0, "skipped": 0, "collected": 516},
        "has_body": True,
        "header_only": False,
    }
    delta = {"pct": 100.0, "changed_files": 6, "total_files": 6, "details": []}
    signals = {
        "exhaustive_read": True,
        "open_task": True,
        "plan_os": True,
        "blast_radius": True,
        "edit_safe": True,
        "verify_bundle": True,
        "claim_done": True,
        "council": True,
        "security": True,
        "visual_critic": True,
        "screenshot_count": 1,
        "marathon": True,
        "hay_chars": 100,
    }
    dims, meta = score_dimensions(oracle, delta, signals)
    assert dims["1_code_correctness"] == 100.0
    assert meta["overall_score"] == 100.0
