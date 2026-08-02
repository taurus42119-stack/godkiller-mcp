"""Browser tool preference — chrome-devtools first when listed on the host.

GODKILLER cannot call peer MCP servers. When chrome-devtools is configured on
the host, ``gk_browser`` refuses by default and tells the agent to use that peer.
Fallback to Playwright ``gk_browser`` only when chrome-devtools is absent
(or force / env override).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

_CDT_NAMES = (
    "chrome-devtools",
    "chrome_devtools",
    "chrome-devtools-mcp",
    "user-chrome-devtools",
)


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def prefer_gk_browser_forced() -> bool:
    """Operator override: always allow Playwright path."""
    return _truthy("GODKILLER_PREFER_GK_BROWSER")


def listed_mcp_server_names() -> List[str]:
    from godkiller_mcp.honesty import mcp_config_candidates, _read_server_names

    names: List[str] = []
    seen = set()
    for path in mcp_config_candidates():
        cfg = _read_server_names(path)
        for n in cfg.get("servers") or []:
            key = str(n).strip().lower()
            if key and key not in seen:
                seen.add(key)
                names.append(str(n))
    return names


def chrome_devtools_listed(names: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
    pool = names if names is not None else listed_mcp_server_names()
    lower = {str(n).strip().lower(): str(n) for n in pool}
    for cand in _CDT_NAMES:
        if cand in lower:
            return True, lower[cand]
    # fuzzy: any server name containing chrome-devtools
    for key, orig in lower.items():
        if "chrome-devtools" in key or key.endswith("chrome_devtools"):
            return True, orig
    return False, None


def browser_preference_status() -> Dict[str, Any]:
    names = listed_mcp_server_names()
    has_cdt, cdt_name = chrome_devtools_listed(names)
    forced = prefer_gk_browser_forced()
    if has_cdt and not forced:
        primary = "chrome-devtools"
        fallback = "gk_browser"
        mouth = (
            f"browser primary={cdt_name or 'chrome-devtools'} "
            "(gk_browser blocked unless force_gk_browser=1 / GODKILLER_PREFER_GK_BROWSER=1)"
        )
    else:
        primary = "gk_browser"
        fallback = None
        mouth = (
            "browser primary=gk_browser (Playwright) — chrome-devtools not listed on host"
            if not has_cdt
            else "browser primary=gk_browser (GODKILLER_PREFER_GK_BROWSER=1)"
        )
    return {
        "primary": primary,
        "fallback": fallback,
        "chrome_devtools_listed": has_cdt,
        "chrome_devtools_name": cdt_name,
        "prefer_gk_browser_env": forced,
        "host_servers_n": len(names),
        "mouth": mouth,
    }


def gk_browser_gate(arguments: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Return redirect payload if gk_browser must yield to chrome-devtools; else None."""
    args = arguments or {}
    if prefer_gk_browser_forced():
        return None
    if str(args.get("force_gk_browser") or "").strip().lower() in ("1", "true", "yes", "on"):
        return None
    if bool(args.get("force_gk_browser") is True):
        return None

    has_cdt, cdt_name = chrome_devtools_listed()
    if not has_cdt:
        return None

    name = cdt_name or "chrome-devtools"
    return {
        "ok": False,
        "allowed": False,
        "error": "prefer_chrome_devtools",
        "preferred": name,
        "fallback": "gk_browser",
        "reason": (
            f"Host lists MCP server {name!r} — use that for browser/debug/UI "
            f"(navigate, snapshot, screenshot, network, console). "
            f"gk_browser is Playwright fallback only when chrome-devtools is absent."
        ),
        "how": (
            f"Call the host tool from server {name!r}. "
            "To force Playwright anyway: pass force_gk_browser=1 on this action "
            "or set GODKILLER_PREFER_GK_BROWSER=1."
        ),
        "then": (
            "After shots exist on disk, attach via gk_evidence.visual_step / "
            "capture_shot / visual_critic for claim armor."
        ),
    }
