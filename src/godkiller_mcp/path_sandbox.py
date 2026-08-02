"""Workspace path + slug sandbox for local MCP (Beta proof-kernel)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class WorkspaceRootError(ValueError):
    """cwd is $HOME (or equivalent) without GODKILLER_WORKSPACE pin."""


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def pinned_workspace_env() -> Optional[Path]:
    raw = os.environ.get("GODKILLER_WORKSPACE", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _authorized_workspace_root() -> Path:
    """Pin or cwd only — never an attacker-supplied path."""
    pinned = pinned_workspace_env()
    if pinned is not None:
        return pinned

    cwd = Path.cwd().resolve()
    home = Path.home().resolve()
    if cwd == home and not _truthy_env("GODKILLER_ALLOW_HOME_WORKSPACE"):
        raise WorkspaceRootError(
            "workspace_root_unpinned: cwd is $HOME; set GODKILLER_WORKSPACE "
            "to the project root (refusing to treat the entire user profile "
            "as the MCP sandbox)"
        )
    return cwd


def workspace_root(explicit: Optional[Union[str, Path]] = None) -> Path:
    """Resolve sandbox root.

    Authorized root = ``GODKILLER_WORKSPACE`` pin, else ``Path.cwd()``
    (refuses bare ``$HOME`` unless ``GODKILLER_ALLOW_HOME_WORKSPACE=1``).

    ``explicit`` may only *confirm* that authorized root — it cannot rebind
    the jail to ``$HOME`` or any other attacker-chosen directory.
    """
    auth = _authorized_workspace_root()
    if explicit is None:
        return auth
    cand = Path(explicit).expanduser().resolve()
    if cand != auth:
        raise ValueError(
            f"workspace_root_rebinding_refused: explicit={cand} authorized={auth} "
            "(path_gate root= cannot widen or replace the pin/cwd jail)"
        )
    return auth


def workspace_status() -> Dict[str, Any]:
    """Compact root report for gk_meta.status (never invent a safe jail)."""
    pinned = pinned_workspace_env()
    try:
        root = workspace_root()
        return {
            "ok": True,
            "root": str(root),
            "pinned": pinned is not None,
            "source": "GODKILLER_WORKSPACE" if pinned is not None else "cwd",
            "home_cwd_blocked": False,
        }
    except WorkspaceRootError as exc:
        return {
            "ok": False,
            "root": None,
            "pinned": False,
            "source": "unpinned_home",
            "home_cwd_blocked": True,
            "error": "workspace_root_unpinned",
            "detail": str(exc),
            "cwd": str(Path.cwd().resolve()),
            "home": str(Path.home().resolve()),
            "fix": "Set GODKILLER_WORKSPACE to the project directory in host MCP env.",
        }


def normalize_slug(slug: str) -> str:
    """Single-segment slug — reject .. / \\ and absolute escapes."""
    raw = str(slug).strip()
    if not raw or any(ch in raw for ch in ("..", "/", "\\", ":", "\0")):
        raise ValueError(f"illegal slug: {slug!r}")
    if not _SLUG_RE.fullmatch(raw):
        raise ValueError(f"illegal slug: {slug!r}")
    return raw


def normalize_artifact_name(name: str) -> str:
    """Safe filename fragment for journey/artifact labels."""
    raw = str(name).strip()
    if not raw or any(ch in raw for ch in ("..", "/", "\\", ":", "\0")):
        raise ValueError(f"illegal artifact name: {name!r}")
    if not _NAME_RE.fullmatch(raw):
        raise ValueError(f"illegal artifact name: {name!r}")
    return raw


def ensure_under_root(
    raw: Union[str, Path],
    root: Optional[Union[str, Path]] = None,
) -> Path:
    """Resolve path and require it stays under root. Raises ValueError on escape."""
    from godkiller_mcp.code_intel import check_edit_safe

    base = workspace_root(root)
    gate = check_edit_safe([str(raw)], base)
    payload = gate.payload or {}
    if not payload.get("safe"):
        reasons = payload.get("reasons") or [f"outside_workspace:{raw}"]
        raise ValueError(f"path_outside_workspace: {', '.join(str(r) for r in reasons)}")
    resolved = payload.get("resolved") or []
    if not resolved:
        raise ValueError(f"path_outside_workspace: {raw!r}")
    return Path(resolved[0])


def path_gate_error(
    raw: Union[str, Path],
    root: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Return JSON error payload if path escapes; else None.

    ``root`` cannot rebind the jail — it must match the authorized pin/cwd
    or the call fails closed (``workspace_root_rebinding_refused``).
    """
    try:
        ensure_under_root(raw, root)
        return None
    except WorkspaceRootError as exc:
        st = workspace_status()
        return {
            "ok": False,
            "error": "workspace_root_unpinned",
            "detail": str(exc),
            "workspace": st.get("cwd") or str(Path.cwd().resolve()),
            "fix": st.get("fix"),
        }
    except ValueError as exc:
        msg = str(exc)
        if "workspace_root_rebinding_refused" in msg:
            try:
                ws = str(workspace_root())
            except WorkspaceRootError:
                ws = str(Path.cwd().resolve())
            return {
                "ok": False,
                "error": "workspace_root_rebinding_refused",
                "detail": msg,
                "workspace": ws,
            }
        try:
            ws = str(workspace_root())
        except WorkspaceRootError:
            ws = str(Path.cwd().resolve())
        return {
            "ok": False,
            "error": "path_outside_workspace",
            "detail": msg,
            "workspace": ws,
        }


def gate_paths(
    paths: Sequence[Union[str, Path]],
    root: Optional[Union[str, Path]] = None,
) -> Tuple[Optional[List[Path]], Optional[Dict[str, Any]]]:
    """Gate many paths. Returns (resolved_list, None) or (None, error_payload)."""
    resolved: List[Path] = []
    for raw in paths:
        err = path_gate_error(raw, root)
        if err:
            return None, err
        resolved.append(ensure_under_root(raw, root))
    return resolved, None
