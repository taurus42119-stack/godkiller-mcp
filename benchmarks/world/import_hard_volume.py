"""
Build Track A hard volume (~1000 pytest cases) for GODKILLER_WORLD_ARENA.

Default: procedural hard pack (honest label: not official LiveCodeBench leaderboard).
Optional: --from-lcb after `pip install 'datasets>=2.20,<4'` when HF load works.

  python -m benchmarks.world.import_hard_volume --target 1000
"""

from __future__ import annotations

import argparse
import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_ROOT = Path(
    os.environ.get(
        "GODKILLER_WORLD_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_WORLD_ARENA"),
    )
)


def _stub_fn(i: int) -> str:
    # Intentionally wrong / incomplete — agent must implement
    return (
        f"def solve_{i}(n: int) -> int:\n"
        f"    \"\"\"Hard volume #{i}: return n*(n+1)//2 (triangular). Stub is wrong.\"\"\"\n"
        f"    return n  # BUG: wrong formula\n"
    )


def _oracle_test(i: int) -> str:
    return (
        f"def test_solve_{i}():\n"
        f"    from volume_pack import solve_{i}\n"
        f"    assert solve_{i}(0) == 0\n"
        f"    assert solve_{i}(1) == 1\n"
        f"    assert solve_{i}(10) == 55\n"
        f"    assert solve_{i}(100) == 5050\n"
    )


def write_pack(root: Path, target: int) -> dict:
    lcb = root / "lcb"
    orig = lcb / "1_ORIGINAL"
    oracle = lcb / "hidden_oracle"
    orig.mkdir(parents=True, exist_ok=True)
    oracle.mkdir(parents=True, exist_ok=True)

    pack_lines = [
        '"""GODKILLER World Track A — hard volume pack (procedural)."""',
        "",
        "PACK_META = {",
        '    "kind": "godkiller_hard_volume",',
        '    "not_official_livecodebench_leaderboard": True,',
        f'    "target": {target},',
        "}",
        "",
    ]
    for i in range(1, target + 1):
        pack_lines.append(_stub_fn(i))
        pack_lines.append("")

    (orig / "volume_pack.py").write_text("\n".join(pack_lines), encoding="utf-8")
    (orig / "README.md").write_text(
        textwrap.dedent(
            f"""\
            # World Track A — hard volume ({target})

            Implement correct `solve_k` in `volume_pack.py`.
            Do **not** open `../hidden_oracle/`.
            Machine score: `score_world` (collected ≥ {target}).
            This pack is an internal harsh volume — not an official LiveCodeBench submission score.
            """
        ),
        encoding="utf-8",
    )

    # Split oracle into shards of 200 for pytest collection speed/clarity
    shard = 200
    shard_files = []
    for start in range(1, target + 1, shard):
        end = min(target, start + shard - 1)
        name = f"test_volume_{start:04d}_{end:04d}.py"
        body = [
            "import sys",
            "from pathlib import Path",
            "",
            "# Arm under test is cwd parent challenge root when pytest is launched by score_world",
            "ROOT = Path(__file__).resolve().parents[1]",
            # score_world will put arm on path
            "",
        ]
        for i in range(start, end + 1):
            body.append(_oracle_test(i))
            body.append("")
        (oracle / name).write_text("\n".join(body), encoding="utf-8")
        shard_files.append(name)

    # conftest: inject arm path
    (oracle / "conftest.py").write_text(
        textwrap.dedent(
            """\
            import os
            import sys
            from pathlib import Path

            def pytest_configure():
                arm = os.environ.get("GODKILLER_WORLD_ARM_PATH", "")
                if arm:
                    sys.path.insert(0, arm)
            """
        ),
        encoding="utf-8",
    )

    manifest = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "kind": "godkiller_hard_volume",
        "not_official_livecodebench_leaderboard": True,
        "original": str((orig / "volume_pack.py").resolve()),
        "oracle_shards": shard_files,
    }
    (lcb / "volume_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def sync_arms(root: Path, arms: tuple[str, ...] = ("2_WITH_MCP", "3_WITHOUT_MCP")) -> dict:
    import shutil

    src = root / "lcb" / "1_ORIGINAL"
    out = {}
    for arm in arms:
        dst = root / "lcb" / arm
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        out[arm] = str(dst.resolve())
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arena-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--target", type=int, default=1000)
    p.add_argument("--sync-arms", action="store_true", default=True)
    args = p.parse_args()
    args.arena_root.mkdir(parents=True, exist_ok=True)
    man = write_pack(args.arena_root, args.target)
    synced = sync_arms(args.arena_root) if args.sync_arms else {}
    print(json.dumps({"manifest": man, "synced": synced}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
