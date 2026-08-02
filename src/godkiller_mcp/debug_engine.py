""" /debug Self-CTF — adversarial *signal heuristics* on THIS workspace only.

Honest mouth: **self_ctf_signal** — NOT a real debugger, NOT dynamic AST execution,
NOT fuzzing. Each tick = SecurityScanEngine + token/string search heuristics
(e.g. TODO/FIXME/password/shell=True/eval). Findings are signals for humans/tests
to verify — never claim root-cause from CTF ticks alone.
Never targets the open internet. No org/domain hunting.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from godkiller_mcp.ship_mode import env_disables, relax_enabled

_META_KEY = "debug_self_ctf"
_SIGNAL_MOUTH = (
    "self_ctf_signal: static scan + token heuristics only — "
    "not dynamic AST execution / not fuzzing / not a debugger"
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_ctf(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (meta or {}).get(_META_KEY) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def start(
    *,
    workspace: str,
    goal: str = "",
    max_rounds: int = 8,
    task_id: str = "",
) -> Dict[str, Any]:
    root = str(Path(workspace).resolve())
    max_rounds = max(1, min(int(max_rounds or 8), 40))
    state = {
        "workspace": root,
        "goal": (goal or "")[:2000],
        "task_id": task_id,
        "max_rounds": max_rounds,
        "round": 0,
        "findings": [],
        "history": [],
        "status": "armed",
        "started_at": _utcnow(),
        "updated_at": _utcnow(),
        "scope": "workspace_only",
        "forbidden": ["open_internet_attack", "third_party_org_hunt"],
        "method": "signal_heuristics",
        "honest": _SIGNAL_MOUTH,
        "not": ["real_debugger", "dynamic_ast_execution", "fuzzing"],
    }
    return {
        "ok": True,
        "source": "debug_self_ctf_start",
        "server_authored": True,
        "honest": _SIGNAL_MOUTH,
        "ctf": state,
    }


def tick(state: Dict[str, Any]) -> Dict[str, Any]:
    """One adversarial *signal* round (static scan + token search) — not a debugger."""
    if state.get("status") in ("passed", "exhausted"):
        return {
            "ok": True,
            "ctf": state,
            "note": f"already {state.get('status')}",
            "honest": _SIGNAL_MOUTH,
        }

    root = Path(str(state.get("workspace") or ".")).resolve()
    if not root.exists():
        return {"ok": False, "reason": f"workspace missing: {root}", "ctf": state}

    rnd = int(state.get("round") or 0) + 1
    state["round"] = rnd
    max_r = int(state.get("max_rounds") or 8)
    goal = str(state.get("goal") or "")

    new_findings: List[Dict[str, Any]] = []
    # 1) Static security scan (local files only)
    try:
        from godkiller_mcp.code_intel import SecurityScanEngine

        scan = SecurityScanEngine().scan(target_path=str(root), severity_threshold="low")
        for issue in (scan.get("issues") or [])[:20]:
            new_findings.append(
                {
                    "kind": "security_scan",
                    "round": rnd,
                    "severity": str(issue.get("severity") or "medium"),
                    "path": str(issue.get("file") or issue.get("path") or "")[:300],
                    "text": str(issue.get("issue") or issue.get("message") or issue)[:500],
                }
            )
    except Exception as exc:
        state.setdefault("history", []).append({"round": rnd, "scan_error": str(exc)[:200]})

    # 2) Goal-token search for suspects
    try:
        from godkiller_mcp.code_intel import HyperSearchEngine

        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", goal)[:6]
        if not tokens:
            # Default heuristic token set — not a vulnerability oracle
            tokens = ["TODO", "FIXME", "password", "shell=True", "eval("]
            state.setdefault("history", []).append(
                {
                    "round": rnd,
                    "note": "default_token_heuristics",
                    "honest": _SIGNAL_MOUTH,
                }
            )
        searcher = HyperSearchEngine()
        for tok in tokens:
            res = searcher.search(tok, search_path=str(root), max_results=6)
            for h in (res.get("matches") or [])[:4]:
                if not isinstance(h, dict):
                    continue
                path = str(h.get("file") or h.get("path") or "")
                # confine
                try:
                    Path(path).resolve().relative_to(root)
                except Exception:
                    if path and not path.startswith(str(root)):
                        continue
                new_findings.append(
                    {
                        "kind": "search_hit",
                        "round": rnd,
                        "severity": "low",
                        "path": path[:300],
                        "text": f"{tok}: {str(h.get('text') or '')[:240]}",
                    }
                )
    except Exception as exc:
        state.setdefault("history", []).append({"round": rnd, "search_error": str(exc)[:200]})

    # Dedupe by path+text prefix
    seen = {(f.get("path"), (f.get("text") or "")[:80]) for f in state.get("findings") or []}
    added = 0
    for f in new_findings:
        key = (f.get("path"), (f.get("text") or "")[:80])
        if key in seen:
            continue
        seen.add(key)
        state.setdefault("findings", []).append(f)
        added += 1

    state.setdefault("history", []).append(
        {"round": rnd, "added": added, "total_findings": len(state.get("findings") or []), "at": _utcnow()}
    )
    state["updated_at"] = _utcnow()

    if state.get("findings"):
        state["status"] = "findings"
        return {
            "ok": True,
            "source": "debug_self_ctf_tick",
            "server_authored": True,
            "honest": _SIGNAL_MOUTH,
            "ctf": state,
            "added": added,
            "next": (
                "signals only — reproduce with failing evidence/tests, then fix; "
                "do not treat CTF hits as root-cause proof"
            ),
        }

    if rnd >= max_r:
        state["status"] = "exhausted"
        return {
            "ok": True,
            "source": "debug_self_ctf_tick",
            "server_authored": True,
            "honest": _SIGNAL_MOUTH,
            "ctf": state,
            "added": 0,
            "next": "No findings after max_rounds — change goal tokens or deepen scan; do not claim fixed",
        }

    state["status"] = "armed"
    return {
        "ok": True,
        "source": "debug_self_ctf_tick",
        "server_authored": True,
        "honest": _SIGNAL_MOUTH,
        "ctf": state,
        "added": 0,
        "next": f"No finding this round — call debug_self_ctf_tick again ({rnd}/{max_r})",
        "force_continue": True,
    }


def run_until(
    state: Dict[str, Any],
    *,
    link_fault_probe: bool = True,
    stop_on_findings: bool = True,
) -> Dict[str, Any]:
    """Tick until findings, max_rounds, or terminal status. Optional fault_probe attach."""
    ticks: List[Dict[str, Any]] = []
    last: Dict[str, Any] = {"ok": True, "ctf": state, "added": 0}
    max_r = max(1, min(int(state.get("max_rounds") or 8), 40))
    # Cap loop iterations hard (defense vs corrupted state)
    for _ in range(max_r + 1):
        if state.get("status") in ("passed", "exhausted", "findings") and state.get("round"):
            if state.get("status") == "findings" and stop_on_findings:
                break
            if state.get("status") in ("passed", "exhausted"):
                break
        last = tick(state)
        ticks.append(
            {
                "round": (last.get("ctf") or state).get("round"),
                "added": last.get("added"),
                "status": (last.get("ctf") or state).get("status"),
            }
        )
        state = last.get("ctf") or state
        if not last.get("ok"):
            break
        if stop_on_findings and state.get("findings") and state.get("status") == "findings":
            break
        if state.get("status") in ("exhausted", "passed"):
            break

    out: Dict[str, Any] = {
        "ok": bool(last.get("ok", True)),
        "source": "debug_self_ctf_run_until",
        "server_authored": True,
        "ctf": state,
        "ticks": ticks,
        "rounds_run": len(ticks),
        "next": last.get("next")
        or (
            "findings ready — reproduce then fix"
            if state.get("status") == "findings"
            else "exhausted or blocked"
        ),
    }

    if link_fault_probe and state.get("findings"):
        try:
            from godkiller_mcp.fault_probe import run_fault_probe

            paths = []
            for f in state.get("findings") or []:
                p = str(f.get("path") or "").strip()
                if p and p.endswith(".py") and p not in paths:
                    paths.append(p)
                if len(paths) >= 8:
                    break
            if paths:
                probe = run_fault_probe(
                    workspace=str(state.get("workspace") or "."),
                    targets=paths,
                )
                payload = probe.to_payload() if hasattr(probe, "to_payload") else dict(probe)
                out["fault_probe"] = payload
                state["fault_probe"] = {
                    "clean": bool(payload.get("clean")),
                    "survivors": len(payload.get("survivors") or []),
                    "at": _utcnow(),
                }
                out["ctf"] = state
        except Exception as exc:
            out["fault_probe_error"] = str(exc)[:300]

    return out


def require_self_ctf_before_fix(state) -> Tuple[bool, str]:
    """Block edit/fix until Self-CTF has findings (or relax / disabled)."""
    if relax_enabled():
        return True, "self_ctf skipped (DEV_RELAX)"
    if env_disables("GODKILLER_DEBUG_CTF"):
        return True, "self_ctf disabled (relax only)"

    meta = getattr(getattr(state, "handle", None), "metadata", None) or {}
    required = meta.get("require_self_ctf") is True or os.environ.get(
        "GODKILLER_DEBUG_CTF_REQUIRED", ""
    ).strip().lower() in ("1", "true", "yes", "on")
    # Also required when mode is debug
    if meta.get("mode") == "debug":
        required = True
    if not required:
        return True, "self_ctf not required"

    ctf = get_ctf(meta)
    if (ctf.get("findings") or []) and ctf.get("status") in ("findings", "passed"):
        return True, "self_ctf has findings"
    # Allow if classic reproduce evidence already present
    types = set()
    try:
        types = set(state.evidence_types())
    except Exception:
        pass
    from godkiller_mcp.schema import EvidenceType

    if EvidenceType.FAILING_TEST in types or EvidenceType.EXIT_CODE in types:
        return True, "reproduce evidence present"
    return (
        False,
        "Forced /debug Self-CTF: debug_self_ctf_start → tick until findings "
        "(workspace only) before fix edits",
    )
