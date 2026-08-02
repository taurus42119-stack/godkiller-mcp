"""Honest mouth — disk truth over model narration.

Default gk_meta.status is ultra-compact (no repeated config dumps).
Pass detail=true or GODKILLER_VERBOSE=1 for full maps / per-path configs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from godkiller_mcp.compact_io import verbose_enabled


def _home() -> Path:
    return Path.home()


def mcp_config_candidates() -> List[Path]:
    h = _home()
    return [
        h / ".gemini" / "config" / "mcp_config.json",
        h / ".gemini" / "antigravity" / "mcp_config.json",
        h / ".gemini" / "antigravity" / "mcp" / "mcp_config.json",
        h / ".gemini" / "antigravity-ide" / "mcp_config.json",
    ]


def _read_server_names(path: Path, *, detail: bool = False) -> Dict[str, Any]:
    out: Dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        out["servers"] = []
        out["error"] = "missing"
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        servers = data.get("mcpServers") or data.get("servers") or {}
        if not isinstance(servers, dict):
            out["servers"] = []
            out["error"] = "mcpServers not an object"
            return out
        names = sorted(servers.keys())
        out["servers"] = names
        out["has_godkiller"] = any("godkiller" in n.lower() for n in names)
        if detail:
            hints = {}
            for name, cfg in servers.items():
                if not isinstance(cfg, dict):
                    hints[name] = {"type": type(cfg).__name__}
                    continue
                hints[name] = {
                    "command": cfg.get("command"),
                    "args": cfg.get("args"),
                    "cwd": cfg.get("cwd"),
                }
            out["launch_hints"] = hints
    except Exception as e:
        out["servers"] = []
        out["error"] = str(e)
    return out


def facade_inventory(*, detail: bool = False) -> Dict[str, Any]:
    from godkiller_mcp.server import FACADE_ACTIONS, FACADE_DESC
    from godkiller_mcp.skill_catalog import build_catalog, resolve_skill_roots

    roots = resolve_skill_roots()
    cat = build_catalog(roots)
    facades = sorted(FACADE_ACTIONS.keys())
    actions_n = sum(len(v) for v in FACADE_ACTIONS.values())
    if not detail:
        return {
            "facades": facades,
            "actions_n": actions_n,
            "skills_n": len(cat),
            "skills_root": str(roots[0]) if roots else None,
        }
    return {
        "facades": facades,
        "action_counts": {k: len(v) for k, v in sorted(FACADE_ACTIONS.items())},
        "actions": {k: sorted(v.keys()) for k, v in FACADE_ACTIONS.items()},
        "descriptions": dict(FACADE_DESC),
        "skill_roots": [str(r) for r in roots],
        "skills_indexed": len(cat),
        "agent_ops_indexed": sum(1 for e in cat if e.get("family") == "agent-ops"),
        "note": "Wrong action returns allowed list.",
    }


def runtime_flags(*, detail: bool = False) -> Dict[str, Any]:
    from godkiller_mcp.ship_mode import profile, relax_enabled

    seal = bool(os.environ.get("GODKILLER_SEAL_KEY", "").strip())
    legacy = os.environ.get("GODKILLER_ALLOW_LEGACY_SEAL", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not detail:
        return {
            "profile": profile(),
            "seal": seal,
            "relax": relax_enabled(),
        }
    return {
        "profile": profile(),
        "dev_relax": relax_enabled(),
        "seal_key_present": seal,
        "allow_legacy_seal": legacy,
        "not_enterprise": True,
        "not_builtin_os_protocol": True,
        "compact_default": True,
    }


def honesty_rules(*, detail: bool = False) -> List[str]:
    core = [
        "Never invent MCP/tool names or scores — call tools / read disk.",
        "Never claim Enterprise/SOC2/SSO or 'built into Antigravity OS'.",
        "Never claim GREEN/claim_done/beat-X without sealed gates.",
        "Helpers (scan/heal/council) ≠ audits. Vision size-only ≠ claim-grade.",
        "Read agents_md before edits/claim; UI needs visual_step sequence.",
    ]
    if not detail:
        return core[:3]
    return core + [
        "tool_propose search≠install; approve≠installed.",
        "If configs disagree across paths, report disagreement.",
        "Human 'looks nice' is not a machine gate unless scorers say so.",
        ".agents + GODKILLER are a paired pack — skill_catalog; do not skip constitution.",
        "Intensity: harsh on MCP claim path; weak on native Write until write-guard PROVEN.",
        "PROFILE=ship blocks claim_done until GODKILLER_WRITE_GUARD_PROVEN=1 (host attest).",
        "Browser: chrome-devtools first when listed on host; gk_browser = Playwright fallback.",
        "Search gate = server evidence required — not automatic exhaustive/read_full.",
        "exhaustive_read requires symbol intel (jcodemunch/map/search digest) first.",
        "write_guard hook_hint_only ≠ OS Write lock.",
    ]


def _host_mcp_summary(present: List[Dict[str, Any]], *, detail: bool) -> Dict[str, Any]:
    name_sets = [tuple(c.get("servers") or []) for c in present]
    consistent = len(set(name_sets)) <= 1 if name_sets else True
    # Prefer longest non-empty server list as canonical
    servers: List[str] = []
    for c in present:
        s = list(c.get("servers") or [])
        if len(s) > len(servers):
            servers = s
    any_gk = any(c.get("has_godkiller") for c in present)
    if not detail:
        return {
            "servers": servers,
            "configs_n": len(present),
            "agree": consistent,
            "godkiller": any_gk,
        }
    return {
        "servers": servers,
        "configs_n": len(present),
        "agree": consistent,
        "godkiller": any_gk,
        "paths": [c.get("path") for c in present],
        "per_config": present,
    }


def build_honesty_status(*, detail: bool = False) -> Dict[str, Any]:
    from godkiller_mcp.agents_constitution import constitution_status
    from godkiller_mcp.path_sandbox import workspace_status
    from godkiller_mcp.write_guard import write_guard_host_status

    detail = verbose_enabled(detail)
    configs = [_read_server_names(p, detail=detail) for p in mcp_config_candidates()]
    present = [c for c in configs if c.get("exists")]
    host = _host_mcp_summary(present, detail=detail)
    agents_full = constitution_status()
    guard = write_guard_host_status()
    workspace = workspace_status()
    if not detail:
        guard = {
            "severity": guard.get("severity"),
            "hook_hint_only": guard.get("hook_hint_only"),
            "wired_hint": guard.get("wired_hint"),
            "proven": guard.get("proven"),
            "msg": guard.get("msg"),
        }
        workspace = {
            "ok": workspace.get("ok"),
            "root": workspace.get("root"),
            "pinned": workspace.get("pinned"),
            "source": workspace.get("source"),
            "error": workspace.get("error"),
        }

    if guard.get("proven"):
        wg_mouth = "write-guard PROVEN"
    elif guard.get("hook_hint_only"):
        wg_mouth = "write-guard hook_hint_only — native Write may bypass"
    else:
        wg_mouth = "write-guard WARN — native Write bypasses MCP"

    from godkiller_mcp.browser_preference import browser_preference_status

    browser_pref = browser_preference_status()
    br_mouth = browser_pref.get("mouth") or ""

    ws_mouth = (
        "workspace pinned"
        if workspace.get("ok") and workspace.get("pinned")
        else (
            "workspace UNPINNED_HOME — set GODKILLER_WORKSPACE"
            if workspace.get("error") == "workspace_root_unpinned"
            else "workspace=cwd"
        )
    )

    if not detail:
        return {
            "ok": True,
            "product": "godkiller-mcp",
            "posture": "beta_proof_kernel",
            "not": ["enterprise_ready", "multi_tenant", "os_lock", "sso_siem_mesh"],
            "compact": True,
            "agents_md": agents_full.get("agents_md_path"),
            "agents_ok": bool(agents_full.get("exists")),
            "visual_qa_rule_8": bool(agents_full.get("has_visual_qa_rule_8")),
            "runtime": runtime_flags(detail=False),
            "workspace": workspace,
            "facades": facade_inventory(detail=False),
            "host_mcp": host,
            "write_guard": guard,
            "browser": {
                "primary": browser_pref.get("primary"),
                "chrome_devtools_listed": browser_pref.get("chrome_devtools_listed"),
            },
            "mouth": (
                "Beta proof-kernel (local MCP); disk>chat; no invent names/scores; "
                "not multi-tenant/SSO/SIEM; detail=true for full maps; "
                f"{ws_mouth}; {wg_mouth}; {br_mouth}"
            ),
        }

    return {
        "ok": True,
        "product": "godkiller-mcp",
        "role": "MCP proof kernel",
        "posture": "beta_proof_kernel",
        "not": ["enterprise_ready", "multi_tenant", "os_lock", "sso_siem_mesh"],
        "compact": False,
        "honesty_rules": honesty_rules(detail=True),
        "agents_constitution": agents_full,
        "runtime": runtime_flags(detail=True),
        "workspace": workspace,
        "this_server_facades": facade_inventory(detail=True),
        "host_mcp": host,
        "host_mcp_configs": configs,
        "configs_agree_on_server_names": host.get("agree"),
        "godkiller_listed_in_any_config": host.get("godkiller"),
        "write_guard": guard,
        "browser": browser_pref,
        "token_hint": "detail=true payload. Default status is ultra-compact.",
        "truth": (
            "Host MCP inventory = config files. This process = facades only. "
            "Chat that disagrees is wrong. "
            "write_guard hook_hint_only until GODKILLER_WRITE_GUARD_PROVEN — "
            "native Write bypasses MCP without live PreToolUse. "
            "Sandbox root = GODKILLER_WORKSPACE or cwd (never unpinned $HOME). "
            "Browser: chrome-devtools first when listed; gk_browser = Playwright fallback. "
            "Local single-process MCP — not multi-tenant SaaS."
        ),
        "mouth": f"{ws_mouth}; {wg_mouth}; {br_mouth}",
    }
