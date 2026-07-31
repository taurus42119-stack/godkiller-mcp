"""
Grade arena JSON into a multi-dimension scorecard from real pytest counts.

  python -m benchmarks.run_arena
  python -m benchmarks.grade_arena --input benchmarks/arena_logs/arena_run.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IN = ROOT / "benchmarks" / "arena_logs" / "arena_run.json"
DEFAULT_OUT = ROOT / "benchmarks" / "arena_logs" / "graded_scorecard.json"


def grade_run(run: Dict[str, Any]) -> Dict[str, Any]:
    counts = run.get("counts") or {}
    passed = int(counts.get("passed") or 0)
    failed = int(counts.get("failed") or 0)
    skipped = int(counts.get("skipped") or 0)
    collected = int(counts.get("collected") or (passed + failed + skipped))
    duration = float(run.get("duration_seconds") or 0.0)
    output = run.get("pytest_output") or ""
    output_chars = int(run.get("pytest_output_full_chars") or len(output))

    pass_rate = (passed / collected * 100.0) if collected else 0.0
    # Output integrity: must contain node ids or PASSED/FAILED lines, not header-only
    has_body = ("PASSED" in output) or ("FAILED" in output) or ("::" in output)
    header_only = (not has_body) and ("test session starts" in output.lower())

    dimensions = {
        "1_pytest_pass_rate": round(pass_rate, 2),
        "2_collected_tests": collected,
        "3_failed_tests": failed,
        "4_wall_clock_seconds": round(duration, 3),
        "5_output_integrity": 100.0 if has_body and not header_only else 0.0,
        "6_output_chars": output_chars,
    }
    # Overall: pass rate gated by output integrity
    overall = round(pass_rate * (1.0 if dimensions["5_output_integrity"] == 100.0 else 0.0), 2)

    suspicious = []
    if collected >= 100 and duration < 1.0:
        suspicious.append("high_test_count_with_subsecond_duration")
    if header_only:
        suspicious.append("pytest_output_header_only")
    if collected == 0:
        suspicious.append("zero_tests_collected")

    return {
        "arm": run.get("arm"),
        "folder": run.get("folder"),
        "pytest_passed": bool(run.get("pytest_passed")),
        "exit_code": run.get("exit_code"),
        "counts": counts,
        "dimensions": dimensions,
        "overall_score": overall,
        "suspicious_flags": suspicious,
        "summary_line": counts.get("summary_line"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grade GODKILLER arena_run.json")
    parser.add_argument("--input", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    run = raw.get("run") or raw
    graded = {
        "graded_at": datetime.now(timezone.utc).isoformat(),
        "grader": "benchmarks.grade_arena",
        "source": str(args.input.resolve()),
        "result": grade_run(run),
        "note": "Scores derived only from recorded pytest counts + output body checks.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graded, indent=2), encoding="utf-8")
    print(json.dumps(graded["result"], indent=2))
    return 0 if not graded["result"]["suspicious_flags"] and graded["result"]["pytest_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
