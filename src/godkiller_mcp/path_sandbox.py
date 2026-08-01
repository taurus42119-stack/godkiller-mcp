"""Workspace path + slug sandbox for local MCP (Beta proof-kernel)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def workspace_root(explicit: Optional[Union[str, Path]] = None) -> Path:
    if explicit is not None:
        return Path(explicit).resolve()
    return Path.cwd().resolve()


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
    """Return JSON error payload if path escapes; else None."""
    try:
        ensure_under_root(raw, root)
        return None
    except ValueError as exc:
        return {
            "ok": False,
            "error": "path_outside_workspace",
            "detail": str(exc),
            "workspace": str(workspace_root(root)),
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
