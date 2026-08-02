"""Resolve GODKILLER state directories outside the installed package tree."""

from __future__ import annotations

import os
from pathlib import Path


class StateRootError(ValueError):
    """Refused to place mutable state under unpinned $HOME."""


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def resolve_state_root(workspace: str | Path | None = None) -> Path:
    """
    Prefer GODKILLER_HOME, else <workspace>/.godkiller, else GODKILLER_WORKSPACE,
    else <cwd>/.godkiller when cwd is not $HOME.

    Never silently write under ``~/.godkiller`` — that races multi-session and
    treats the user profile as a project. Opt-in only via
    ``GODKILLER_ALLOW_HOME_STATE=1`` (or explicit ``GODKILLER_HOME=~/.godkiller``).

    Never write under site-packages / the installed package path.

    Multi-process: use a distinct GODKILLER_HOME (or workspace) per process.
    RED: sharing one GODKILLER_HOME across concurrent hosts still contends —
    ``tasks.lock`` + ``probe.lock`` are advisory only. Do not claim multi-tenant safety.
    """
    env = os.environ.get("GODKILLER_HOME", "").strip()
    if env:
        root = Path(env).expanduser().resolve()
    elif workspace is not None and str(workspace).strip():
        root = Path(workspace).expanduser().resolve() / ".godkiller"
    else:
        pinned_ws = os.environ.get("GODKILLER_WORKSPACE", "").strip()
        if pinned_ws:
            root = Path(pinned_ws).expanduser().resolve() / ".godkiller"
        else:
            cwd = Path.cwd().resolve()
            home = Path.home().resolve()
            if cwd == home:
                if _truthy("GODKILLER_ALLOW_HOME_STATE"):
                    root = home / ".godkiller"
                else:
                    raise StateRootError(
                        "state_root_unpinned: cwd is $HOME and neither GODKILLER_HOME "
                        "nor GODKILLER_WORKSPACE is set — refusing ~/.godkiller fallback. "
                        "Set GODKILLER_HOME or GODKILLER_WORKSPACE to the project, "
                        "or GODKILLER_ALLOW_HOME_STATE=1 only if intentional."
                    )
            root = cwd / ".godkiller"
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
