"""
Reproducible arena runner — writes full pytest output + counts + wall time.

Usage (from repo root):
  python -m benchmarks.run_arena
  python -m benchmarks.run_arena --arm with_mcp --workspace path/to/arm
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GAUNTLET = ROOT  # full suite: tests/ + benchmarks/gauntlet/
OUT_DIR = ROOT / "benchmarks" / "arena_logs"


def _parse_pytest_counts(output: str) -> dict:
    # e.g. "12 passed in 0.71s" / "1 failed, 2 passed in 1.2s"
    passed = failed = skipped = 0
    m = re.search(
        r"(?:(\d+)\s+failed)?(?:,\s*)?(?:(\d+)\s+passed)?(?:,\s*)?(?:(\d+)\s+skipped)?",
        output.splitlines()[-1] if output.strip() else "",
    )
    # Prefer summary line containing "passed" or "failed"
    summary = ""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
            break
    mp = re.search(r"(\d+)\s+passed", summary)
    mf = re.search(r"(\d+)\s+failed", summary)
    ms = re.search(r"(\d+)\s+skipped", summary)
    if mp:
        passed = int(mp.group(1))
    if mf:
        failed = int(mf.group(1))
    if ms:
        skipped = int(ms.group(1))
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "collected": passed + failed + skipped,
        "summary_line": summary,
    }


def run_arm(name: str, test_path: Path, timeout_sec: int = 120) -> dict:
    test_path = test_path.resolve()
    started = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--tb=line", "tests", "benchmarks/gauntlet"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    duration = time.perf_counter() - started
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    counts = _parse_pytest_counts(output)
    return {
        "arm": name,
        "folder": str(test_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
        "exit_code": proc.returncode,
        "pytest_passed": proc.returncode == 0,
        "counts": counts,
        "pytest_output": output[-12000:],
        "pytest_output_full_chars": len(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="GODKILLER reproducible arena runner")
    parser.add_argument(
        "--gauntlet",
        type=Path,
        default=DEFAULT_GAUNTLET,
        help="Directory of pytest files for the gauntlet",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR / "arena_run.json",
        help="Output JSON path",
    )
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    result = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "benchmarks.run_arena",
        "note": (
            "This file is produced by a real pytest invocation. "
            "Do not treat legacy hand-written scorecards as reproducible without this runner."
        ),
        "gauntlet": str(args.gauntlet.resolve()),
        "run": run_arm("gauntlet", args.gauntlet),
    }
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(args.out), "counts": result["run"]["counts"], "duration": result["run"]["duration_seconds"]}, indent=2))
    return 0 if result["run"]["pytest_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
