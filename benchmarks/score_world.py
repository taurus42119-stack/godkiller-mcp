"""
World Track A scorer — volume hard pack / LCB-shaped arena.

  python -m benchmarks.score_world --arm 3_WITHOUT_MCP
  python -m benchmarks.score_world --compare

Hard bar: pytest collected >= volume target (default 1000 from manifest).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


DEFAULT_ARENA = Path(
    os.environ.get(
        "GODKILLER_WORLD_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_WORLD_ARENA"),
    )
)


def _load_target(arena: Path) -> int:
    man = arena / "lcb" / "volume_manifest.json"
    if man.is_file():
        return int(json.loads(man.read_text(encoding="utf-8")).get("target") or 1000)
    return 1000


def _parse_pytest(output: str) -> dict:
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


def score_arm(arena: Path, arm: str) -> Dict[str, Any]:
    target = _load_target(arena)
    arm_path = arena / "lcb" / arm
    oracle = arena / "lcb" / "hidden_oracle"
    logs = arena / "lcb" / "logs" / arm
    logs.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["GODKILLER_WORLD_ARM_PATH"] = str(arm_path.resolve())
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(oracle),
        "-q",
        "--tb=no",
    ]
    try:
        p = subprocess.run(
            cmd,
            cwd=str(arm_path),
            capture_output=True,
            timeout=600,
            env=env,
        )
        out = (p.stdout or b"").decode("utf-8", errors="replace") + (
            p.stderr or b""
        ).decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as e:
        out = f"timeout: {e}"
        p = None  # type: ignore

    counts = _parse_pytest(out)
    collected = counts["collected"]
    passed = counts["passed"]
    volume_ok = collected >= target
    pass_rate = (passed / collected) if collected else 0.0

    # delta: any change from 1_ORIGINAL volume_pack
    import hashlib

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""

    base = arena / "lcb" / "1_ORIGINAL" / "volume_pack.py"
    cur = arm_path / "volume_pack.py"
    delta = sha(base) != sha(cur)

    result = {
        "arm": arm,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "target_volume": target,
        "oracle": counts,
        "volume_gate": volume_ok,
        "pass_rate": pass_rate,
        "delta_from_original": delta,
        "suspicious_zero_delta_pass": (pass_rate > 0.9 and not delta),
        "hard_pass": bool(volume_ok and pass_rate >= 0.95 and delta),
        "mouth": (
            "Internal World Track A volume score — not an official LiveCodeBench "
            "leaderboard result unless ATTRIBUTION says official harness was used."
        ),
        "pytest_tail": out[-2500:],
    }
    receipt = logs / "score_world.json"
    receipt.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["receipt"] = str(receipt)
    return result


def compare(arena: Path) -> dict:
    arms = ("2_WITH_MCP", "3_WITHOUT_MCP")
    rows = {}
    for a in arms:
        p = arena / "lcb" / "logs" / a / "score_world.json"
        if p.is_file():
            rows[a] = json.loads(p.read_text(encoding="utf-8"))
    summary = {
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "arms": {
            a: {
                "hard_pass": rows.get(a, {}).get("hard_pass"),
                "pass_rate": rows.get(a, {}).get("pass_rate"),
                "collected": (rows.get(a, {}).get("oracle") or {}).get("collected"),
                "delta": rows.get(a, {}).get("delta_from_original"),
            }
            for a in arms
        },
        "mouth": "Not an official LCB public leaderboard claim.",
    }
    out = arena / "lcb" / "logs" / "score_world_compare.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["receipt"] = str(out)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    ap.add_argument("--arm", choices=("2_WITH_MCP", "3_WITHOUT_MCP", "both"), default=None)
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    if args.compare and not args.arm:
        print(json.dumps(compare(args.arena_root), indent=2))
        return 0
    if args.arm is None:
        ap.error("provide --arm or --compare")
    arms = ("2_WITH_MCP", "3_WITHOUT_MCP") if args.arm == "both" else (args.arm,)
    payload = {"results": {a: score_arm(args.arena_root, a) for a in arms}}
    if len(arms) == 2 or args.compare:
        payload["compare"] = compare(args.arena_root)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
