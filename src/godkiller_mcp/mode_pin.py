"""Active mode pin — hard policy for host write-guard + edit_safe.

Persisted under workspace/.godkiller/active_mode.json (HMAC-sealed).
No machine-specific paths. English-only reasons.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

# Modes that must not native-Write application code
READISH = frozenset({"ask", "view", "verify", "jury"})
# Plan may write plan artifacts only
PLAN_PREFIXES = (".agents/plans/",)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_mode(mode: str) -> str:
    return str(mode or "").strip().lower().lstrip("/")


def mode_path(workspace: str | Path) -> Path:
    ws = Path(workspace).resolve()
    root = ws / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    return root / "active_mode.json"


def _body(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace": data.get("workspace"),
        "mode": _norm_mode(str(data.get("mode") or "")),
        "task_id": str(data.get("task_id") or ""),
        "updated_at": str(data.get("updated_at") or ""),
    }


def _seal(payload: Dict[str, Any], *, workspace: str | Path) -> Dict[str, Any]:
    import hashlib
    import hmac as hm

    from godkiller_mcp.evidence_integrity import load_or_create_seal_key
    from godkiller_mcp.runtime_paths import tasks_dir

    body = _body(payload)
    key = load_or_create_seal_key(tasks_dir())
    material = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    dig = hm.new(key, material, hashlib.sha256).hexdigest()
    out = dict(body)
    out["hmac"] = dig
    out["seal_alg"] = "hmac-sha256"
    return out


def _verify(data: Dict[str, Any], *, workspace: str | Path) -> bool:
    import hashlib
    import hmac as hm

    raw = str(data.get("hmac") or "").strip()
    if not raw:
        return False
    try:
        from godkiller_mcp.evidence_integrity import load_or_create_seal_key
        from godkiller_mcp.runtime_paths import tasks_dir

        key = load_or_create_seal_key(tasks_dir())
    except Exception:
        return False
    material = json.dumps(_body(data), sort_keys=True, separators=(",", ":")).encode("utf-8")
    expect = hm.new(key, material, hashlib.sha256).hexdigest()
    return hm.compare_digest(expect, raw)


def persist_active_mode(
    workspace: str | Path,
    mode: str,
    *,
    task_id: str = "",
) -> Path:
    ws = Path(workspace).resolve()
    path = mode_path(ws)
    payload = {
        "workspace": str(ws),
        "mode": _norm_mode(mode),
        "task_id": task_id,
        "updated_at": _utcnow(),
    }
    sealed = _seal(payload, workspace=ws)
    path.write_text(json.dumps(sealed, indent=2), encoding="utf-8")
    return path


def load_active_mode(workspace: str | Path) -> Dict[str, Any]:
    path = mode_path(workspace)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict) or not _verify(data, workspace=workspace):
        return {}
    try:
        sealed_ws = Path(str(data.get("workspace") or "")).expanduser().resolve()
        if sealed_ws != Path(workspace).resolve():
            return {}
    except OSError:
        return {}
    return data


def mode_blocks_native_write(mode: str, rel_path: str) -> tuple[bool, str]:
    """Return (blocked, reason). blocked=True → deny Write."""
    m = _norm_mode(mode)
    rel = str(rel_path or "").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    if not m:
        return False, ""
    if m in READISH:
        return (
            True,
            f"mode={m} forbids native Write/Edit — activate /ultradeep or /debug after /plan",
        )
    if m == "plan":
        if any(rel == p.rstrip("/") or rel.startswith(p) for p in PLAN_PREFIXES):
            return False, ""
        return (
            True,
            "mode=plan allows writes only under .agents/plans/ — no application code",
        )
    return False, ""


def mode_blocks_edit_safe(mode: str) -> tuple[bool, str]:
    m = _norm_mode(mode)
    if m in READISH or m == "plan":
        return (
            True,
            f"mode={m} forbids check_edit_safe / app edits — finish ritual or switch mode",
        )
    return False, ""


def apply_mode_activation(
    workspace: str | Path,
    mode: str,
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Pin mode + reset write allowlist for the mode's policy."""
    from godkiller_mcp.write_guard import end_write_turn, persist_allow_paths

    m = _norm_mode(mode)
    pin = persist_active_mode(workspace, m, task_id=task_id)
    write: Dict[str, Any]
    if m == "plan":
        dest = persist_allow_paths(
            workspace,
            [".agents/plans"],
            task_id=task_id,
            phase="plan",
            force=True,
            source="mode_pin",
        )
        write = {
            "ok": True,
            "path": str(dest),
            "paths": [".agents/plans"],
            "hint": "plan mode: native Write only under .agents/plans/",
        }
    elif m in READISH or m in ("ultradeep", "debug"):
        write = end_write_turn(workspace, task_id=task_id)
        write["hint"] = (
            f"mode={m}: native Write cleared. "
            + (
                "Read-only until /plan or /ultradeep."
                if m in READISH
                else "Call set_paths / ultradeep_plan_file before Write."
            )
        )
    else:
        write = {"skipped": True}
    return {
        "ok": True,
        "mode": m,
        "mode_pin": str(pin),
        "write": write,
    }
