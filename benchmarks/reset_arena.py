"""
Reset arena arms to the sealed buggy baseline (1_ORIGINAL).

  python -m benchmarks.reset_arena
  python -m benchmarks.reset_arena --arm 3_WITHOUT_MCP
  python -m benchmarks.reset_arena --arm 2_WITH_MCP

Copies challenge .py from 1_ORIGINAL into the arm.
Preserves .agents / .gemini on 2_WITH_MCP (MCP scaffold).
Does NOT touch hidden_oracle/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ARENA = Path(
    os.environ.get(
        "GODKILLER_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_ISOLATED_ARENA"),
    )
)

CHALLENGE_FILES = (
    "app.py",
    "nightmare_app.py",
    "anthropic_sota.py",
    "tier_1_easy_50.py",
    "tier_2_medium_150.py",
    "tier_3_hard_300.py",
)

PRESERVE_DIRS = (".agents", ".gemini")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def reset_arm(arena_root: Path, arm: str) -> dict:
    src = arena_root / "1_ORIGINAL"
    dst = arena_root / arm
    if not src.is_dir():
        raise FileNotFoundError(f"Missing baseline: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    copied = []
    for name in CHALLENGE_FILES:
        s = src / name
        if not s.is_file():
            raise FileNotFoundError(f"Baseline missing file: {s}")
        d = dst / name
        shutil.copy2(s, d)
        copied.append({"file": name, "sha256_16": _sha(d)})

    # Drop stale summary that claims 516/516 after a reset
    for junk in ("bare_ai_summary.txt",):
        p = dst / junk
        if p.exists():
            p.unlink()

    preserved = [p for p in PRESERVE_DIRS if (dst / p).exists()]
    return {
        "arm": arm,
        "baseline": str(src.resolve()),
        "folder": str(dst.resolve()),
        "copied": copied,
        "preserved_dirs": preserved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset arena arms to 1_ORIGINAL")
    parser.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    parser.add_argument(
        "--arm",
        choices=("2_WITH_MCP", "3_WITHOUT_MCP", "both"),
        default="both",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON receipt path",
    )
    args = parser.parse_args()

    arms = ("2_WITH_MCP", "3_WITHOUT_MCP") if args.arm == "both" else (args.arm,)
    receipt = {
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "arena_root": str(args.arena_root.resolve()),
        "arms": {a: reset_arm(args.arena_root, a) for a in arms},
        "note": "Challenge files restored from 1_ORIGINAL. Oracle untouched. Ready for Antigravity A/B.",
    }

    out = args.out
    if out is None:
        out = args.arena_root / "logs" / "last_reset.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
