"""Grade arena + scorer integrity tests."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.grade_arena import grade_run


def test_grader_flags_header_only_and_suspicious_516_shape():
    fake = {
        "arm": "legacy",
        "duration_seconds": 0.38,
        "pytest_passed": True,
        "counts": {
            "passed": 516,
            "failed": 0,
            "skipped": 0,
            "collected": 516,
            "summary_line": "516 passed in 0.38s",
        },
        "pytest_output": "============================= test session starts =============================\nplatform win32",
        "pytest_output_full_chars": 80,
    }
    g = grade_run(fake)
    assert "high_test_count_with_subsecond_duration" in g["suspicious_flags"]
    assert "pytest_output_header_only" in g["suspicious_flags"]
    assert g["dimensions"]["5_output_integrity"] == 0.0
    assert g["overall_score"] == 0.0


def test_grader_accepts_real_body(tmp_path: Path):
    run = {
        "arm": "gauntlet",
        "duration_seconds": 0.9,
        "pytest_passed": True,
        "counts": {"passed": 12, "failed": 0, "skipped": 0, "collected": 12, "summary_line": "12 passed"},
        "pytest_output": "tests/foo.py::test_a PASSED\n============================= 12 passed in 0.9s =============================",
        "pytest_output_full_chars": 200,
    }
    g = grade_run(run)
    assert g["suspicious_flags"] == []
    assert g["overall_score"] == 100.0
