"""Write guard — MCP + host-hook enforcement for native Write/Edit.

MCP alone cannot intercept IDE Write. This module is the policy brain:
host PreToolUse hooks call it (CLI or MCP tool) before bytes hit disk.

Returns host-compatible PreToolUse hook decisions:
  permissionDecision: allow | deny
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


_SKIP_PREFIXES = (
    ".git/",
    ".venv/",
    "venv/",
    "node_modules/",
    "__pycache__/",
)


def _norm_rel(path: Path, workspace: Path) -> Optional[str]:
    try:
        rel = path.resolve().relative_to(workspace.resolve())
    except ValueError:
        return None
    return str(rel).replace("\\", "/")


def extract_paths_from_plan_text(text: str) -> List[str]:
    """Pull path-like tokens from plan step bodies."""
    if not text:
        return []
    found = re.findall(
        r"(?:[\w.-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|md|json|toml|yml|yaml|css|html)",
        text,
        flags=re.I,
    )
    return list(dict.fromkeys(found))


def collect_allow_paths(state=None, *, explicit: Optional[Sequence[str]] = None) -> List[str]:
    """Collect allow paths for MCP write_guard checks.

    When ultradeep_file_gate is enabled, ONLY the current file may be allowed —
    never the full queue (that previously let agents native-Write every Phase file
    in one turn).
    """
    out: List[str] = []
    if explicit:
        out.extend(str(p).replace("\\", "/").lstrip("./") for p in explicit if p)
    if state is not None:
        meta = state.handle.metadata or {}
        gate = meta.get("ultradeep_file_gate") or {}
        if isinstance(gate, dict) and gate.get("enabled"):
            # Hard: current file only, and only once think→plan reached edit/verify.
            out.extend(ultradeep_active_write_paths(gate))
        else:
            for key in ("write_allow_paths", "allowed_write_paths"):
                raw = meta.get(key) or []
                if isinstance(raw, str):
                    raw = [raw]
                out.extend(str(p).replace("\\", "/").lstrip("./") for p in raw if p)
            # Do NOT harvest every path-looking token from plan text into the
            # native-write allowlist — that widened the jail across all Phases.
    seen = set()
    uniq = []
    for p in out:
        p = p.lstrip("./")
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def ultradeep_active_write_paths(gate: Dict[str, Any]) -> List[str]:
    """Paths native Write may touch under an armed ultradeep gate (0 or 1 file)."""
    if not isinstance(gate, dict) or not gate.get("enabled"):
        return []
    cur = gate.get("current") or gate.get("current_path")
    if not cur:
        return []
    path = str(cur).replace("\\", "/").lstrip("./")
    entry = (gate.get("files") or {}).get(path) or {}
    stage = str(entry.get("stage") or "")
    # Deny native writes during think/plan — force ritual before bytes.
    if stage not in ("edit", "verify"):
        return []
    return [path]


def max_write_paths() -> int:
    """Ship posture defaults to 1 path per turn; override via GODKILLER_WRITE_MAX_PATHS."""
    raw = os.environ.get("GODKILLER_WRITE_MAX_PATHS", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    try:
        from godkiller_mcp.ship_mode import ship_mode

        return 1 if ship_mode() else 8
    except Exception:
        return 1


def _write_allow_path(workspace: str | Path) -> Path:
    ws = Path(workspace).resolve()
    root = ws / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    return root / "write_allow.json"


def load_write_allow(workspace: str | Path) -> Dict[str, Any]:
    path = _write_allow_path(workspace)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    if not _verify_write_allow(data, workspace=workspace):
        return {}
    return data


def ultradeep_sync_write_allow(
    workspace: str | Path,
    gate: Dict[str, Any],
    *,
    task_id: str = "",
) -> Dict[str, Any]:
    """Force disk allowlist to ultradeep current-only (bypasses turn re-arm lock)."""
    paths = ultradeep_active_write_paths(gate)
    phase = f"ultradeep:{paths[0]}" if paths else "ultradeep:locked"
    dest = persist_allow_paths(
        workspace,
        paths,
        task_id=task_id,
        phase=phase,
        force=True,
        source="ultradeep",
    )
    return {
        "ok": True,
        "path": str(dest),
        "paths": list(paths),
        "phase": phase,
        "hint": (
            "Native Write allowed for current ultradeep file only "
            "(empty while think/plan). Call end_turn / advance before the next file."
            if paths
            else "Native Write locked until ultradeep_plan_file reaches edit stage."
        ),
    }


def decide_write(
    *,
    path: str,
    workspace: str | Path,
    allow_paths: Optional[Sequence[str]] = None,
    require_allowlist: bool = True,
    tool_name: str = "Write",
) -> Dict[str, Any]:
    """
    Fail-closed when require_allowlist and allow_paths is non-empty:
    path must match an allow entry (exact or under prefix).

    If allow_paths empty and require_allowlist: deny (no envelope = no write).
    If require_allowlist False: allow any path under workspace only.
    """
    ws = Path(workspace).resolve()
    raw = Path(path)
    candidate = raw if raw.is_absolute() else (ws / raw)
    rel = _norm_rel(candidate, ws)
    if rel is None:
        return _deny(
            f"write_guard DENY: path outside workspace ({path})",
            tool_name=tool_name,
        )
    if any(rel.startswith(s) or f"/{s}" in f"/{rel}" for s in _SKIP_PREFIXES):
        return _deny(f"write_guard DENY: protected path {rel}", tool_name=tool_name)

    allowed = [a.lstrip("./").replace("\\", "/") for a in (allow_paths or []) if a]
    if require_allowlist:
        if not allowed:
            return _deny(
                "write_guard DENY: empty write allowlist — set paths via "
                "write_guard.set_paths / plan / ultradeep queue before native Write",
                tool_name=tool_name,
            )
        ok = False
        for a in allowed:
            # Exact path or directory prefix only — never basename-only (evil/config.py vs config.py)
            if rel == a or rel.startswith(a.rstrip("/") + "/"):
                ok = True
                break
        if not ok:
            return _deny(
                f"write_guard DENY: {rel} not in allowlist ({len(allowed)} entries)",
                tool_name=tool_name,
                extra={"path": rel, "allow_paths": allowed[:40]},
            )

    return {
        "allowed": True,
        "permissionDecision": "allow",
        "reason": f"write_guard ALLOW: {rel}",
        "path": rel,
        "workspace": str(ws),
        "tool_name": tool_name,
        "hookSpecificOutput": {
            "permissionDecision": "allow",
            "permissionDecisionReason": f"write_guard ALLOW: {rel}",
        },
    }


def _deny(reason: str, *, tool_name: str, extra: Optional[dict] = None) -> Dict[str, Any]:
    out = {
        "allowed": False,
        "permissionDecision": "deny",
        "reason": reason,
        "tool_name": tool_name,
        "hookSpecificOutput": {
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        },
    }
    if extra:
        out.update(extra)
    return out


def decide_from_hook_event(event: Dict[str, Any], *, workspace: Optional[str] = None) -> Dict[str, Any]:
    """Parse PreToolUse JSON from stdin (host hook payload)."""
    tool = str(event.get("tool_name") or event.get("tool") or "Write")
    inp = event.get("tool_input") or event.get("input") or {}
    path = (
        inp.get("file_path")
        or inp.get("path")
        or inp.get("target_file")
        or event.get("file_path")
        or ""
    )
    # Authorized jail: GODKILLER_WORKSPACE pin if set, else hook cwd/workspace — never sealed rebind
    ws = _authorized_hook_workspace(workspace=workspace, event=event)
    allow = event.get("allow_paths") or []
    # Optional on-disk envelope — only trust HMAC-sealed write_allow.json
    env_path = Path(ws) / ".godkiller" / "write_allow.json"
    if env_path.exists():
        try:
            data = json.loads(env_path.read_text(encoding="utf-8"))
            if not _verify_write_allow(data, workspace=ws):
                # Tampered / unsigned — ignore paths (fail closed for allowlist expansion)
                data = {}
            else:
                sealed_ws_raw = data.get("workspace")
                if not sealed_ws_raw:
                    data = {}
                else:
                    try:
                        sealed_ws = Path(str(sealed_ws_raw)).expanduser().resolve()
                    except OSError:
                        sealed_ws = None
                    auth = Path(ws).resolve()
                    if sealed_ws is None or sealed_ws != auth:
                        # P0: sealed envelope must match authorized root — never widen jail
                        data = {}
                    else:
                        allow = list(allow) + list(data.get("paths") or [])
                        # Intentionally do NOT reassign ws from sealed payload
        except (OSError, json.JSONDecodeError):
            pass
    require = True
    from godkiller_mcp.ship_mode import env_disables

    if env_disables("GODKILLER_WRITE_GUARD", default_on="1"):
        require = False
    return decide_write(
        path=str(path),
        workspace=ws,
        allow_paths=allow,
        require_allowlist=require,
        tool_name=tool,
    )


def _authorized_hook_workspace(
    *,
    workspace: Optional[str] = None,
    event: Optional[Dict[str, Any]] = None,
) -> str:
    """Resolve hook jail without trusting sealed write_allow.workspace."""
    event = event or {}
    pinned = os.environ.get("GODKILLER_WORKSPACE", "").strip()
    if pinned:
        return str(Path(pinned).expanduser().resolve())
    raw = workspace or event.get("cwd") or event.get("workspace") or os.getcwd()
    return str(Path(str(raw)).expanduser().resolve())


def _allow_body_for_seal(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace": data.get("workspace"),
        "task_id": data.get("task_id") or "",
        "paths": list(data.get("paths") or []),
        "phase": str(data.get("phase") or ""),
        "turn_open": bool(data.get("turn_open", True)),
        "source": str(data.get("source") or ""),
    }


def _seal_write_allow(payload: Dict[str, Any], *, workspace: str | Path) -> Dict[str, Any]:
    """Attach HMAC using GODKILLER_SEAL_KEY (same family as evidence seals)."""
    import hashlib
    import hmac as hm

    from godkiller_mcp.evidence_integrity import load_or_create_seal_key
    from godkiller_mcp.runtime_paths import tasks_dir

    body = _allow_body_for_seal(payload)
    key = load_or_create_seal_key(tasks_dir())
    material = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    dig = hm.new(key, material, hashlib.sha256).hexdigest()
    out = dict(body)
    out["hmac"] = dig
    out["seal_alg"] = "hmac-sha256"
    return out


def _verify_write_allow(data: Dict[str, Any], *, workspace: str | Path) -> bool:
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
    body = _allow_body_for_seal(data)
    material = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expect = hm.new(key, material, hashlib.sha256).hexdigest()
    return hm.compare_digest(expect, raw)


def persist_allow_paths(
    workspace: str | Path,
    paths: Sequence[str],
    *,
    task_id: str = "",
    phase: str = "",
    force: bool = False,
    source: str = "set_paths",
) -> Path:
    """Seal write allowlist to disk.

    Turn lock (unless force=True / source in ultradeep|end_turn):
    if a turn is already open with a non-empty allowlist, refuse to re-arm
    with a different path set — caller must end_write_turn() first.
    This is what stops Phase 1+2+3 native Write rushes in one agent turn.
    """
    ws = Path(workspace).resolve()
    path = _write_allow_path(ws)
    clean = [str(p).replace("\\", "/").lstrip("./") for p in paths if p]
    clean = list(dict.fromkeys(clean))
    cap = max_write_paths()
    if len(clean) > cap and source == "set_paths" and not force:
        raise ValueError(
            f"write_guard set_paths capped at {cap} path(s) per turn "
            f"(got {len(clean)}). Finish this turn with gk_guard.end_turn, "
            f"or set GODKILLER_WRITE_MAX_PATHS (relax only helps outside ship)."
        )

    existing = load_write_allow(ws)
    if (
        not force
        and source == "set_paths"
        and existing.get("turn_open")
        and list(existing.get("paths") or [])
    ):
        old = [str(p).replace("\\", "/").lstrip("./") for p in (existing.get("paths") or [])]
        old_phase = str(existing.get("phase") or "")
        new_phase = str(phase or old_phase or "turn")
        # Same phase + identical or subset paths: allow shrink/refresh.
        if new_phase == old_phase and set(clean).issubset(set(old)):
            pass
        else:
            raise ValueError(
                "write_guard turn still open — call gk_guard.end_turn before "
                "set_paths for a new Phase/path set. "
                f"(open_phase={old_phase or 'turn'!r}, open_paths={old[:8]})"
            )

    turn_open = bool(clean) if source != "end_turn" else False
    phase_s = str(phase or existing.get("phase") or ("turn" if clean else ""))
    if source == "end_turn":
        phase_s = str(existing.get("phase") or phase_s)
        clean = []
        turn_open = False

    payload = {
        "workspace": str(ws),
        "task_id": task_id or str(existing.get("task_id") or ""),
        "paths": clean,
        "phase": phase_s,
        "turn_open": turn_open,
        "source": source,
    }
    sealed = _seal_write_allow(payload, workspace=ws)
    path.write_text(json.dumps(sealed, indent=2), encoding="utf-8")
    return path


def end_write_turn(workspace: str | Path, *, task_id: str = "") -> Dict[str, Any]:
    """Close the write turn: empty allowlist → native Write denies until set_paths again."""
    dest = persist_allow_paths(
        workspace,
        [],
        task_id=task_id,
        force=True,
        source="end_turn",
    )
    return {
        "ok": True,
        "path": str(dest),
        "paths": [],
        "turn_open": False,
        "hint": (
            "Write turn closed. Native Write is denied until gk_guard.set_paths "
            "for the NEXT Phase only. End the host turn / schedule wake before continuing."
        ),
    }


def _host_marker_path() -> Path:
    return Path.home() / ".godkiller" / "write_guard_host.json"


def mark_write_guard_wired(*, source: str = "install") -> Path:
    """Record that sync/install dropped hook artifacts (not OS enforcement proof)."""
    path = _host_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "wired_hint": True,
        "source": source,
        "command": "godkiller-write-guard --stdin",
        "honest": "Marker means hook files were installed or env set — not that the IDE enforces.",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_guard_host_status() -> Dict[str, Any]:
    """Fail-loud probe for gk_meta.status — hint ≠ enforcement.

    File/env markers only prove hook *artifacts* may exist. Native Write stays
    unblocked until the host actually invokes PreToolUse → write_guard.
    Set ``GODKILLER_WRITE_GUARD_PROVEN=1`` only after a live deny/allow test.
    """
    env_on = os.environ.get("GODKILLER_WRITE_GUARD_WIRED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    proven = os.environ.get("GODKILLER_WRITE_GUARD_PROVEN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    marker = _host_marker_path()
    marker_ok = False
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            marker_ok = bool(data.get("wired_hint"))
        except (OSError, json.JSONDecodeError):
            marker_ok = False

    home = Path.home()
    hook_hits: list[str] = []
    scan_paths = [
        Path.cwd() / ".agents" / "hooks.json",
        Path.cwd() / ".agents" / "hooks" / "godkiller-write-guard.hooks.json",
        Path.cwd() / ".agents" / "hooks" / "antigravity_pretooluse_write_guard.json",
        Path.cwd() / ".godkiller" / "pretooluse_write_guard.json",
        Path.cwd() / ".antigravity" / "hooks" / "pretooluse_write_guard.json",
        home / ".godkiller" / "write_guard_host.json",
    ]
    needles = ("write_guard", "godkiller-write-guard", "pretooluse_write_guard")
    for p in scan_paths:
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(n in text for n in needles):
            hook_hits.append(str(p))

    wired = env_on or marker_ok or bool(hook_hits)
    if proven:
        return {
            "severity": "ok",
            "hook_hint_only": False,
            "wired_hint": True,
            "proven": True,
            "env": env_on,
            "marker": marker_ok,
            "hook_files_n": len(hook_hits),
            "msg": (
                "write-guard marked PROVEN via GODKILLER_WRITE_GUARD_PROVEN "
                "(operator attested live PreToolUse)"
            ),
        }
    if wired:
        return {
            "severity": "warn",
            "hook_hint_only": True,
            "wired_hint": True,
            "proven": False,
            "env": env_on,
            "marker": marker_ok,
            "hook_files_n": len(hook_hits),
            "msg": (
                "FAIL-LOUD: hook_hint_only — artifact/env hint ≠ enforcement. "
                "Native Write still bypasses MCP until PreToolUse calls "
                "godkiller-write-guard. After a live deny test set "
                "GODKILLER_WRITE_GUARD_PROVEN=1."
            ),
        }
    return {
        "severity": "warn",
        "hook_hint_only": True,
        "wired_hint": False,
        "proven": False,
        "env": False,
        "marker": False,
        "hook_files_n": 0,
        "msg": (
            "FAIL-LOUD: no write-guard heartbeat — native Write bypasses MCP. "
            "Bootstrap: godkiller-bootstrap --workspace . "
            "See docs/WRITE_GUARD_HOOKS.md."
        ),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI for host hooks: install-hint / install / stdin decide."""
    import argparse
    import shutil

    parser = argparse.ArgumentParser(description="GODKILLER write_guard (host hook)")
    sub = parser.add_subparsers(dest="cmd")

    p_hint = sub.add_parser("install-hint", help="Print how to wire PreToolUse (no write)")
    p_hint.add_argument("--workspace", default=None)

    p_install = sub.add_parser(
        "install",
        help="Copy hook JSON into .agents / host config path (does not claim enforce)",
    )
    p_install.add_argument("--workspace", default=None)
    p_install.add_argument(
        "--target",
        choices=("agents", "antigravity", "godkiller"),
        default="agents",
        help="Where to drop write-guard hook JSON",
    )
    p_install.add_argument("--force", action="store_true")

    parser.add_argument("--workspace", default=None)
    parser.add_argument("--path", default=None, help="Direct path check (no stdin)")
    parser.add_argument("--allow", action="append", default=[])
    parser.add_argument("--stdin", action="store_true", help="Read hook event JSON from stdin")
    args = parser.parse_args(argv)

    if args.cmd == "install-hint":
        ws = Path(args.workspace or os.getcwd()).resolve()
        print(
            json.dumps(
                {
                    "ok": True,
                    "workspace": str(ws),
                    "command": "godkiller-write-guard --stdin",
                    "python_module": "python -m godkiller_mcp.write_guard --stdin",
                    "hook_artifact": "godkiller_mcp/hooks/antigravity_pretooluse_write_guard.json",
                    "install": "godkiller-bootstrap --workspace .",
                    "honest": (
                        "Without host PreToolUse pointing at this CLI, native Write bypasses MCP. "
                        "bootstrap writes portable .agents files — does not prove enforcement."
                    ),
                    "example_agents_hooks": {
                        "enabled": True,
                        "PreToolUse": [
                            {
                                "matcher": "Write|Edit|NotebookEdit",
                                "command": "godkiller-write-guard --stdin",
                                "timeout": 15,
                            }
                        ],
                    },
                    "merge_into": ".agents/hooks.json",
                },
                indent=2,
            )
        )
        return 0

    if args.cmd == "install":
        # Full project materialization (preferred)
        from godkiller_mcp.bootstrap import bootstrap_workspace

        ws = Path(args.workspace or os.getcwd()).resolve()
        result = bootstrap_workspace(ws, force_agents_md=False)
        # Still drop legacy target copy for godkiller/ profile dirs when requested
        if args.target == "godkiller":
            pkg_hook = Path(__file__).resolve().parent / "hooks" / "antigravity_pretooluse_write_guard.json"
            if not pkg_hook.is_file():
                pkg_hook = Path(__file__).resolve().parent / "hooks" / "pretooluse_write_guard.json"
            dest = ws / ".godkiller" / "pretooluse_write_guard.json"
            if pkg_hook.is_file() and (args.force or not dest.exists()):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pkg_hook, dest)
                result["godkiller_copy"] = str(dest)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.path:
        decision = decide_write(
            path=args.path,
            workspace=args.workspace or os.getcwd(),
            allow_paths=args.allow,
            require_allowlist=bool(args.allow) or True,
        )
    else:
        raw = sys.stdin.read()
        try:
            event = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            event = {}
        if args.allow:
            event["allow_paths"] = list(event.get("allow_paths") or []) + args.allow
        decision = decide_from_hook_event(event, workspace=args.workspace)

    print(json.dumps(decision, ensure_ascii=False))
    # Claude Code: exit 2 = block
    return 0 if decision.get("allowed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
