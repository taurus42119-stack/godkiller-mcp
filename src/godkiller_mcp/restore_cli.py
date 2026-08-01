"""CLI: restore leftover fault_probe mutants after SIGKILL / crash.

Usage:
  godkiller-restore [--workspace PATH] [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="godkiller-restore",
        description="Restore workspace files left mutated by a crashed fault_probe run.",
    )
    parser.add_argument(
        "--workspace",
        "-w",
        default=None,
        help="Workspace root (default: cwd)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only report unclean state; do not restore",
    )
    args = parser.parse_args(argv)
    ws = Path(args.workspace or Path.cwd()).resolve()

    from godkiller_mcp.fault_probe import (
        probe_unclean,
        restore_probe_backups,
        warn_if_probe_unclean,
    )

    unclean = probe_unclean(ws)
    if args.check:
        print(
            json.dumps(
                {
                    "workspace": str(ws),
                    "unclean": unclean,
                    "hint": None
                    if not unclean
                    else "Run: godkiller-restore --workspace .",
                },
                indent=2,
            )
        )
        return 1 if unclean else 0

    warn_if_probe_unclean(ws, stream=sys.stderr)
    if not unclean:
        print(json.dumps({"ok": True, "restored": [], "clean": True, "workspace": str(ws)}))
        return 0

    info = restore_probe_backups(ws)
    info["workspace"] = str(ws)
    info["ok"] = bool(info.get("clean")) and not info.get("errors")
    print(json.dumps(info, indent=2))
    return 0 if info["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
