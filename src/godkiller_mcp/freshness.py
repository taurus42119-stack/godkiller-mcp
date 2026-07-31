"""Freshness — bind evidence to the current on-disk source tree.

If the agent edits after verify, old receipts must not unlock claim_done.
This is the Proof-or-Stop load-bearing rule, GODKILLER-native.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Sequence


_SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".godkiller",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

_CODE_SUFFIXES = {".py", ".pyi", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java"}


def _iter_files(roots: Sequence[Path], *, max_files: int = 2000) -> tuple[List[Path], bool, int]:
    """Collect code files. Returns (files_to_hash, truncated, total_found)."""
    found: List[Path] = []
    for root in roots:
        root = root.resolve()
        if root.is_file():
            found.append(root)
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() not in _CODE_SUFFIXES:
                continue
            found.append(p)
    total = len(found)
    truncated = total > max_files
    # Always prefer a stable sorted set; if truncated, FAIL-CLOSED via complete=False
    # rather than silently omitting later paths (B4 flood attack).
    return found[:max_files], truncated, total


def material_hash(
    paths: Sequence[str | Path],
    *,
    workspace: str | Path | None = None,
    max_files: int = 2000,
) -> dict:
    """
    Canonical SHA-256 over sorted relative paths + file digests.

    Includes a full path-manifest digest so flood+truncate cannot hide edits to
    omitted files without changing the hash envelope. If truncated, complete=False
    and claim/verify must fail closed.
    """
    ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    resolved: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = (ws / p).resolve()
        else:
            p = p.resolve()
        # Paths outside workspace are ignored (no escape into hash)
        try:
            p.relative_to(ws)
        except ValueError:
            continue
        resolved.append(p)

    files, truncated, total_found = _iter_files(resolved, max_files=max_files)

    # Manifest of ALL discovered paths (even those beyond max_files) — need full walk
    all_rels: List[str] = []
    for root in resolved:
        if root.is_file():
            try:
                all_rels.append(str(root.relative_to(ws)).replace("\\", "/"))
            except ValueError:
                pass
            continue
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() not in _CODE_SUFFIXES:
                continue
            try:
                all_rels.append(str(p.relative_to(ws)).replace("\\", "/"))
            except ValueError:
                continue

    manifest = hashlib.sha256("\n".join(sorted(set(all_rels))).encode("utf-8")).hexdigest()

    h = hashlib.sha256()
    h.update(f"manifest:{manifest}\n".encode("utf-8"))
    h.update(f"total:{len(set(all_rels))}\n".encode("utf-8"))
    included = []
    for f in sorted(files, key=lambda x: str(x).lower()):
        try:
            rel = str(f.relative_to(ws)).replace("\\", "/")
        except ValueError:
            continue
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        line = f"{rel}:{digest}\n"
        h.update(line.encode("utf-8"))
        included.append({"path": rel, "sha256": digest})

    complete = not truncated
    return {
        "material_hash": h.hexdigest(),
        "workspace": str(ws),
        "file_count": len(included),
        "total_code_files": len(set(all_rels)),
        "complete": complete,
        "truncated": truncated,
        "manifest_hash": manifest,
        "files": included[:200],
    }


def hash_workspace_code(workspace: str | Path, *, max_files: int = 2000) -> dict:
    ws = Path(workspace).resolve()
    return material_hash([ws], workspace=ws, max_files=max_files)


def hash_touched_or_workspace(state, workspace: str | Path | None = None) -> dict:
    from godkiller_mcp.hollow_surface import paths_touched_in_state

    ws = workspace or Path.cwd()
    touched = paths_touched_in_state(state)
    if touched:
        return material_hash(touched, workspace=ws)
    return hash_workspace_code(ws)


def evidence_fresh_against_disk(
    payload: dict,
    *,
    workspace: str | Path | None = None,
    state=None,
) -> tuple[bool, str]:
    """
    Return (ok, reason). Missing material_hash → not fresh (fail-closed)
    unless GODKILLER_DEV_RELAX=1.
    """
    from godkiller_mcp.ship_mode import env_disables, relax_enabled

    if relax_enabled():
        return True, "freshness skipped (DEV_RELAX)"
    # GODKILLER_FRESHNESS=0 only honored under DEV_RELAX (ship mode ignores it)
    if env_disables("GODKILLER_FRESHNESS"):
        return True, "freshness disabled (relax only)"

    recorded = (payload or {}).get("material_hash")
    if not recorded:
        return False, "evidence missing material_hash — rerun verify_bundle / fault_probe"
    if payload.get("complete") is False or payload.get("truncated") is True:
        return False, "material_hash incomplete/truncated — cannot claim on partial tree hash"

    ws = workspace or Path.cwd()
    # Workspace-scoped receipts always rehash the whole tree (B3 decoy targets)
    if payload.get("material_scope") == "workspace" or payload.get("source") in (
        "verify_bundle",
        "fault_probe",
    ):
        live = hash_workspace_code(ws)
    elif "material_files" in (payload or {}) and payload.get("material_scope") != "workspace":
        paths = [f.get("path") for f in (payload.get("material_files") or []) if f.get("path")]
        live = material_hash(paths, workspace=ws)
    elif payload.get("material_paths"):
        live = material_hash(list(payload["material_paths"]), workspace=ws)
    elif state is not None:
        live = hash_workspace_code(ws)
    else:
        live = hash_workspace_code(ws)

    if not live.get("complete", True):
        return (
            False,
            f"live material_hash incomplete ({live.get('total_code_files')} code files) — "
            "tree exceeds hash budget; shrink workspace",
        )
    if live["material_hash"] != recorded:
        return (
            False,
            "stale evidence: material_hash no longer matches disk "
            f"(recorded={recorded[:12]}… live={live['material_hash'][:12]}…) "
            "— agent edited after verify; rerun proof",
        )
    return True, "fresh"
