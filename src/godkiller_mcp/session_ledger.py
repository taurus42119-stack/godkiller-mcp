"""Session ledger — append-only hash-chained event log under .godkiller/.

Original GODKILLER module. Each row seals the previous digest so rewrites
are detectable. Not a product-name clone of any third-party audit tool.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.runtime_paths import resolve_state_root


GENESIS = "0" * 64


def ledger_path(state_root: Path | None = None) -> Path:
    root = state_root or resolve_state_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / "session_ledger.jsonl"


def _digest(prev: str, body: dict) -> str:
    material = prev + json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _last_digest(path: Path) -> str:
    if not path.is_file() or path.stat().st_size == 0:
        return GENESIS
    last = ""
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                last = line
    if not last:
        return GENESIS
    try:
        row = json.loads(last)
        return str(row.get("digest") or GENESIS)
    except json.JSONDecodeError:
        return GENESIS


def append_ledger(
    event: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    task_id: Optional[str] = None,
    state_root: Path | None = None,
) -> Dict[str, Any]:
    path = ledger_path(state_root)
    prev = _last_digest(path)
    body = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "task_id": task_id,
        "payload": payload or {},
    }
    digest = _digest(prev, body)
    row = {**body, "prev": prev, "digest": digest}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def verify_ledger(state_root: Path | None = None) -> Dict[str, Any]:
    path = ledger_path(state_root)
    if not path.is_file():
        return {"ok": True, "entries": 0, "path": str(path), "reason": "empty"}
    prev = GENESIS
    n = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            body = {
                "ts": row["ts"],
                "event": row["event"],
                "task_id": row.get("task_id"),
                "payload": row.get("payload") or {},
            }
            expect = _digest(prev, body)
            if row.get("prev") != prev or row.get("digest") != expect:
                return {
                    "ok": False,
                    "entries": n,
                    "path": str(path),
                    "reason": f"chain break at entry {n}",
                }
            prev = row["digest"]
            n += 1
    return {"ok": True, "entries": n, "path": str(path), "tip": prev}


def read_ledger_tail(n: int = 20, state_root: Path | None = None) -> List[dict]:
    path = ledger_path(state_root)
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-n:]:
        if line.strip():
            out.append(json.loads(line))
    return out
