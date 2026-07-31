"""
Reproducible arena runner.

Modes:
  isolated (default if arena root exists):
    Run sealed hidden_oracle against
      <root>/2_WITH_MCP  and  <root>/3_WITHOUT_MCP
  engine:
    Run package tests/ + benchmarks/gauntlet

Env:
  GODKILLER_ARENA_ROOT  default ~/Desktop/GODKILLER_ISOLATED_ARENA (override recommended)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "benchmarks" / "arena_logs"
DEFAULT_ISOLATED = Path(
    os.environ.get(
        "GODKILLER_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_ISOLATED_ARENA"),
    )
)

ORACLE_IGNORE = (
    "test_mega_500.py",  # needs mega_500_bugs module not present in arms
    "test_calculator.py",
    "test_financial.py",
)


def _parse_pytest_counts(output: str) -> dict:
    summary = ""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
            break
    passed = failed = skipped = 0
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


def run_pytest(
    *,
    args: list[str],
    cwd: Path,
    env: dict | None = None,
    timeout_sec: int = 300,
    arm: str,
    folder: str,
) -> dict:
    started = time.perf_counter()
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--tb=line", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        env=full_env,
    )
    duration = time.perf_counter() - started
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    counts = _parse_pytest_counts(output)
    return {
        "arm": arm,
        "folder": folder,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(duration, 3),
        "exit_code": proc.returncode,
        "pytest_passed": proc.returncode == 0,
        "counts": counts,
        "pytest_output": output[-200000:],
        "pytest_output_full_chars": len(output),
        "passed_markers_in_log": len(re.findall(r"\bPASSED\b", output)),
    }


def run_isolated(arena_root: Path) -> dict:
    oracle = arena_root / "hidden_oracle"
    if not oracle.is_dir():
        raise FileNotFoundError(f"hidden_oracle not found under {arena_root}")

    ignores = []
    for name in ORACLE_IGNORE:
        p = oracle / name
        if p.exists():
            ignores.extend(["--ignore", str(p)])

    arms = {}
    for arm_name in ("2_WITH_MCP", "3_WITHOUT_MCP"):
        arm_dir = arena_root / arm_name
        if not arm_dir.is_dir():
            raise FileNotFoundError(f"Missing arm folder: {arm_dir}")
        arms[arm_name] = run_pytest(
            args=[str(oracle), *ignores],
            cwd=arena_root,
            env={"PYTHONPATH": str(arm_dir)},
            arm=arm_name,
            folder=str(arm_dir),
        )
    return {
        "mode": "isolated",
        "arena_root": str(arena_root.resolve()),
        "oracle": str(oracle.resolve()),
        "comparison": arms,
    }


def run_engine() -> dict:
    result = run_pytest(
        args=["tests", "benchmarks/gauntlet"],
        cwd=ROOT,
        arm="engine_gauntlet",
        folder=str(ROOT),
    )
    return {"mode": "engine", "run": result}


def main() -> int:
    parser = argparse.ArgumentParser(description="GODKILLER arena runner")
    parser.add_argument(
        "--mode",
        choices=("auto", "isolated", "engine"),
        default="auto",
        help="auto uses isolated when GODKILLER_ISOLATED_ARENA exists",
    )
    parser.add_argument(
        "--arena-root",
        type=Path,
        default=DEFAULT_ISOLATED,
        help="Isolated arena root containing 2_WITH_MCP / 3_WITHOUT_MCP / hidden_oracle",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR / "arena_run.json",
    )
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mode = args.mode
    if mode == "auto":
        mode = "isolated" if (args.arena_root / "hidden_oracle").is_dir() else "engine"

    if mode == "isolated":
        payload = run_isolated(args.arena_root)
        ok = all(v.get("pytest_passed") for v in payload["comparison"].values())
    else:
        payload = run_engine()
        ok = bool(payload["run"]["pytest_passed"])

    doc = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "runner": "benchmarks.run_arena",
        **payload,
    }
    args.out.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    # compact stdout
    if mode == "isolated":
        summary = {
            "wrote": str(args.out),
            "mode": mode,
            "arms": {
                k: {
                    "passed": v["counts"]["passed"],
                    "failed": v["counts"]["failed"],
                    "collected": v["counts"]["collected"],
                    "duration": v["duration_seconds"],
                    "output_chars": v["pytest_output_full_chars"],
                }
                for k, v in payload["comparison"].items()
            },
        }
    else:
        summary = {
            "wrote": str(args.out),
            "mode": mode,
            "counts": payload["run"]["counts"],
            "duration": payload["run"]["duration_seconds"],
        }
    print(json.dumps(summary, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
