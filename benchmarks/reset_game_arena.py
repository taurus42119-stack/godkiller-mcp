"""
Reset GODKILLER_GAME_ARENA arms to 1_ORIGINAL/stub_game.

  python -m benchmarks.reset_game_arena
  python -m benchmarks.reset_game_arena --arm 2_WITH_MCP
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
        "GODKILLER_GAME_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_GAME_ARENA"),
    )
)

PRESERVE_DIRS = (".agents", ".gemini")


def _rmtree(path: Path) -> None:
    """rmtree that tolerates Windows locks (e.g. esbuild.exe still running)."""

    def _onexc(func, p, exc_info):  # noqa: ANN001
        try:
            os.chmod(p, 0o666)
            func(p)
        except OSError:
            # Last resort: rename aside so copytree can proceed
            junk = Path(str(p) + f".__trash_{os.getpid()}")
            try:
                os.replace(p, junk)
            except OSError:
                pass

    if hasattr(shutil, "rmtree"):
        try:
            shutil.rmtree(path, onexc=_onexc)  # py3.12+
        except TypeError:
            shutil.rmtree(path, onerror=lambda f, p, e: _onexc(f, p, e))


def _wipe_except_preserved(dst: Path) -> None:
    if not dst.exists():
        return
    for child in list(dst.iterdir()):
        if child.name in PRESERVE_DIRS:
            continue
        if child.is_dir():
            _rmtree(child)
        else:
            try:
                child.unlink()
            except OSError:
                junk = Path(str(child) + f".__trash_{os.getpid()}")
                try:
                    os.replace(child, junk)
                except OSError:
                    pass


def reset_arm(arena_root: Path, arm: str) -> dict:
    src = arena_root / "1_ORIGINAL" / "stub_game"
    dst_root = arena_root / arm
    dst = dst_root / "game"
    if not src.is_dir():
        raise FileNotFoundError(f"Missing stub template: {src}")
    dst_root.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        _wipe_except_preserved(dst)
        if dst.exists():
            _rmtree(dst)
    if dst.exists():
        # Still locked — rename whole tree and copy fresh stub beside it
        junk = dst_root / f"game.__trash_{os.getpid()}"
        os.replace(dst, junk)
    shutil.copytree(src, dst)

    readme = dst / "README.md"
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        text = text.replace(
            "`../1_ORIGINAL/reference_fps/`\n(from arena root: `1_ORIGINAL/reference_fps/`)",
            "`../../1_ORIGINAL/reference_fps/`",
        )
        readme.write_text(text, encoding="utf-8")

    preserved = [p for p in PRESERVE_DIRS if (dst_root / p).exists()]
    return {
        "arm": arm,
        "stub": str(src.resolve()),
        "folder": str(dst.resolve()),
        "preserved_dirs": preserved,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset game arena arms to stub_game")
    parser.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    parser.add_argument(
        "--arm",
        choices=("2_WITH_MCP", "3_WITHOUT_MCP", "both"),
        default="both",
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    arms = ("2_WITH_MCP", "3_WITHOUT_MCP") if args.arm == "both" else (args.arm,)
    receipt = {
        "reset_at": datetime.now(timezone.utc).isoformat(),
        "arena_root": str(args.arena_root.resolve()),
        "arms": {a: reset_arm(args.arena_root, a) for a in arms},
        "note": "game/ restored from stub_game. reference_fps and hidden_oracle untouched.",
    }
    out = args.out or (args.arena_root / "logs" / "last_reset.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
