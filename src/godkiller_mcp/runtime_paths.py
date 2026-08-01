"""Resolve GODKILLER state directories outside the installed package tree."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_state_root(workspace: str | Path | None = None) -> Path:
    """
    Prefer GODKILLER_HOME, else <workspace>/.godkiller, else ~/.godkiller.
    Never write under site-packages / the installed package path.
    Never dump lessons.db into a random cwd when no workspace is set.

    Multi-process: use a distinct GODKILLER_HOME (or workspace) per process —
    only fault_probe holds an advisory file lock; task/evidence persist does not.
    """
    env = os.environ.get("GODKILLER_HOME", "").strip()
    if env:
        root = Path(env).expanduser().resolve()
    elif workspace:
        root = Path(workspace).resolve() / ".godkiller"
    else:
        root = Path.home().resolve() / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    return root


def tasks_dir(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    path = root / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def marathon_dir(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    path = root / "marathon"
    path.mkdir(parents=True, exist_ok=True)
    return path


def handoff_dir(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    path = root / "handoff"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ui_artifacts_dir(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    path = root / "ui_artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def lessons_db_path(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    return root / "lessons.db"


def package_root() -> Path:
    """Installed package parent (for protocols/.agents only — not for mutable state)."""
    return Path(__file__).resolve().parents[2]


def is_under_package_tree(path: Path) -> bool:
    try:
        path.resolve().relative_to(package_root().resolve())
        return True
    except ValueError:
        return False
