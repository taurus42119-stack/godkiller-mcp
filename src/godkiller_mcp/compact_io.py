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


def dumps_payload(data: Any) -> str:
    """Default: minified JSON. Set GODKILLER_JSON_PRETTY=1 for indent=2."""
    if json_pretty_enabled():
        return json.dumps(data, indent=2, default=str)
    return json.dumps(data, separators=(",", ":"), default=str)


def protocol_preview(text: str, *, max_lines: int = 18, max_chars: int = 1600) -> str:
    lines = (text or "").strip().splitlines()
    chunk = "\n".join(lines[:max_lines])
    if len(lines) > max_lines:
        chunk += f"\n…({len(lines) - max_lines} more lines; call get_protocol or activate include_protocol=true)"
    if len(chunk) > max_chars:
        return chunk[: max_chars - 20] + "\n…(truncated)"
    return chunk
