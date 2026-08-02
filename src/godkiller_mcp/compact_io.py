"""Token budget helpers — compact MCP payloads by default.

Host models re-ingest every tool result. Pretty JSON + full protocol dumps
and maximal-swarm mandates were burning context for no gate benefit.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


def verbose_enabled(explicit: Optional[bool] = None) -> bool:
    if explicit is True:
        return True
    if explicit is False:
        return False
    return os.environ.get("GODKILLER_VERBOSE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def json_pretty_enabled() -> bool:
    return os.environ.get("GODKILLER_JSON_PRETTY", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def dumps_payload(data: Any, *, max_chars: Optional[int] = None) -> str:
    """Default: minified JSON with hard size cap (fail-closed truncate).

    Env ``GODKILLER_PAYLOAD_MAX_CHARS`` overrides default (120_000).
    Oversized payloads set ``truncated:true`` / ``payload_truncated:true`` when
    ``data`` is a dict; otherwise return a compact error object.
    """
    if max_chars is None:
        raw = os.environ.get("GODKILLER_PAYLOAD_MAX_CHARS", "").strip()
        max_chars = int(raw) if raw.isdigit() else 120_000
    if json_pretty_enabled():
        text = json.dumps(data, indent=2, default=str)
    else:
        text = json.dumps(data, separators=(",", ":"), default=str)
    if len(text) <= max_chars:
        return text
    # Fail-closed: never return a 200k+ bomb to the host context.
    if isinstance(data, dict):
        slim = {
            "ok": data.get("ok", False) if "ok" in data else False,
            "error": data.get("error") or "payload_too_large",
            "truncated": True,
            "payload_truncated": True,
            "chars": len(text),
            "max_chars": max_chars,
            "keys": sorted(str(k) for k in list(data.keys())[:40]),
            "msg": (
                f"payload {len(text)} chars exceeds cap {max_chars}; "
                "narrow the request or set GODKILLER_PAYLOAD_MAX_CHARS"
            ),
        }
        for keep in ("task_id", "directive", "reason", "workspace", "path"):
            if keep in data:
                slim[keep] = data[keep]
        out = json.dumps(slim, separators=(",", ":"), default=str)
        if len(out) <= max_chars:
            return out
    err = {
        "ok": False,
        "error": "payload_too_large",
        "truncated": True,
        "chars": len(text),
        "max_chars": max_chars,
    }
    return json.dumps(err, separators=(",", ":"))


def protocol_preview(text: str, *, max_lines: int = 18, max_chars: int = 1600) -> str:
    lines = (text or "").strip().splitlines()
    chunk = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        chunk += f"\n…({len(lines) - max_lines} more lines; call get_protocol or activate include_protocol=true)"
    if len(chunk) > max_chars:
        return chunk[: max_chars - 20] + "\n…(truncated)"
    return chunk
