"""
Reset WORLD arena LCB/hard-volume arms from lcb/1_ORIGINAL.

  python -m benchmarks.reset_world_arena
  python -m benchmarks.reset_world_arena --arm 2_WITH_MCP
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ARENA = Path(
    os.environ.get(
        "GODKILLER_WORLD_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_WORLD_ARENA"),
    )
)


def reset_arm(arena: Path, arm: str) -> dict:
    src = arena / "lcb" / "1_ORIGINAL"
    dst = arena / "lcb" / arm
    if not src.is_dir():
        raise FileNotFoundError(f"missing {src} — run: python -m benchmarks.world.import_hard_volume")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return {"arm": arm, "folder": str(dst.resolve())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    ap.add_argument("--arm", choices=("2_WITH_MCP", "3_WITHOUT_MCP", "both"), default="both")
    args = ap.parse_args()
    arms = ("2_WITH_MCP", "3_WITHOUT_MCP") if args.arm == "both" else (args.arm,)
    receipt = {
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "arena_root": str(args.arena_root.resolve()),
        "arms": {a: reset_arm(args.arena_root, a) for a in arms},
    }
    out = args.arena_root / "lcb" / "logs" / "last_reset.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
