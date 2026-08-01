"""Aggregate Field1/2/3 score receipts into one mega scorecard."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _load(path: Path) -> dict | None:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def build() -> dict:
    iso = Path(os.environ.get("GODKILLER_ARENA_ROOT", str(Path.home() / "Desktop" / "GODKILLER_ISOLATED_ARENA")))
    world = Path(
        os.environ.get("GODKILLER_WORLD_ARENA_ROOT", str(Path.home() / "Desktop" / "GODKILLER_WORLD_ARENA"))
    )
    game = Path(
        os.environ.get("GODKILLER_GAME_ARENA_ROOT", str(Path.home() / "Desktop" / "GODKILLER_GAME_ARENA"))
    )
    card = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "campaign": "MEGA_AB",
        "mouth": (
            "Internal Bare vs GODKILLER campaign across Isolated + World volume + Game. "
            "Not a public LiveCodeBench/SWE-bench leaderboard submission."
        ),
        "fields": {
            "isolated": {
                "bare": _load(iso / "logs" / "score_3_WITHOUT_MCP.json")
                or _load(iso / "logs" / "3_WITHOUT_MCP" / "score_11.json"),
                "with_mcp": _load(iso / "logs" / "score_2_WITH_MCP.json")
                or _load(iso / "logs" / "2_WITH_MCP" / "score_11.json"),
            },
            "world": {
                "bare": _load(world / "lcb" / "logs" / "3_WITHOUT_MCP" / "score_world.json"),
                "with_mcp": _load(world / "lcb" / "logs" / "2_WITH_MCP" / "score_world.json"),
                "compare": _load(world / "lcb" / "logs" / "score_world_compare.json"),
            },
            "game": {
                "bare": _load(game / "logs" / "3_WITHOUT_MCP" / "score_game.json"),
                "with_mcp": _load(game / "logs" / "2_WITH_MCP" / "score_game.json"),
                "compare": _load(game / "logs" / "score_game_compare.json"),
            },
        },
        "harsh_rules": [
            "Same prompt budget per field across arms",
            "No oracle peek",
            "Game FPS median >= 60 and mode != stub",
            "World collected >= target; zero-delta high pass is suspicious",
            "Isolated sealed dims 5-11 require evidence when claiming MCP win",
        ],
    }
    out_dirs = [iso / "logs", world / "lcb" / "logs", game / "logs", Path.home() / "Desktop"]
    paths = []
    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)
        p = d / "mega_scorecard.json"
        p.write_text(json.dumps(card, indent=2), encoding="utf-8")
        paths.append(str(p))
    card["written"] = paths
    return card


def main() -> int:
    argparse.ArgumentParser(description="Write mega_scorecard.json").parse_args()
    print(json.dumps(build(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
