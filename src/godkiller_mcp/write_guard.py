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
    out: List[str] = []
    if explicit:
        out.extend(str(p).replace("\\", "/") for p in explicit if p)
    if state is not None:
        meta = state.handle.metadata or {}
        for key in ("write_allow_paths", "allowed_write_paths"):
            raw = meta.get(key) or []
            if isinstance(raw, str):
                raw = [raw]
            out.extend(str(p).replace("\\", "/") for p in raw if p)
        plan = meta.get("plan_dict") or {}
        if isinstance(plan, dict):
            steps = plan.get("steps") or plan
            blob = " ".join(str(v) for v in steps.values()) if isinstance(steps, dict) else str(plan)
            out.extend(extract_paths_from_plan_text(blob))
        gate = meta.get("ultradeep_file_gate") or {}
        for entry in gate.get("files") or gate.get("queue") or []:
            if isinstance(entry, dict) and entry.get("path"):
                out.append(str(entry["path"]).replace("\\", "/"))
            elif isinstance(entry, str):
                out.append(entry.replace("\\", "/"))
        cur = gate.get("current") or gate.get("current_path")
        if cur:
            out.append(str(cur).replace("\\", "/"))
    # dedupe
    seen = set()
    uniq = []
    for p in out:
        p = p.lstrip("./")
        if p and p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


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


def persist_allow_paths(workspace: str | Path, paths: Sequence[str], *, task_id: str = "") -> Path:
    ws = Path(workspace).resolve()
    root = ws / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "write_allow.json"
    payload = {
        "workspace": str(ws),
        "task_id": task_id,
        "paths": [str(p).replace("\\", "/").lstrip("./") for p in paths if p],
    }
    sealed = _seal_write_allow(payload, workspace=ws)
    path.write_text(json.dumps(sealed, indent=2), encoding="utf-8")
    return path


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
        home / ".cursor" / "hooks" / "pretooluse_write_guard.json",
        home / ".claude" / "settings.json",
        Path.cwd() / ".cursor" / "hooks" / "pretooluse_write_guard.json",
        Path.cwd() / ".claude" / "settings.json",
        Path.cwd() / ".godkiller" / "pretooluse_write_guard.json",
        Path.cwd() / ".agents" / "hooks" / "godkiller-write-guard.hooks.json",
        Path.cwd() / ".agents" / "hooks" / "antigravity_pretooluse_write_guard.json",
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
            "Optional PreToolUse hook: godkiller-write-guard install --target cursor. "
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
        help="Copy hook JSON into .cursor / Antigravity-style config path (does not claim enforce)",
    )
    p_install.add_argument("--workspace", default=None)
    p_install.add_argument(
        "--target",
        choices=("cursor", "antigravity", "godkiller"),
        default="cursor",
        help="Where to drop pretooluse_write_guard.json",
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
                    "hook_artifact": "godkiller_mcp/hooks/pretooluse_write_guard.json",
                    "install": "godkiller-write-guard install --target cursor",
                    "honest": (
                        "Without host PreToolUse pointing at this CLI, native Write bypasses MCP. "
                        "install copies config only — does not prove enforcement."
                    ),
                    "example_cursor": {
                        "hooks": {
                            "PreToolUse": [
                                {
                                    "matcher": "Write|Edit|NotebookEdit",
                                    "command": "godkiller-write-guard --stdin",
                                }
                            ]
                        }
                    },
                },
                indent=2,
            )
        )
        return 0

    if args.cmd == "install":
        ws = Path(args.workspace or os.getcwd()).resolve()
        pkg_hook = Path(__file__).resolve().parent / "hooks" / "pretooluse_write_guard.json"
        if not pkg_hook.is_file():
            print(json.dumps({"ok": False, "reason": f"missing package hook: {pkg_hook}"}))
            return 1
        if args.target == "cursor":
            dest_dir = ws / ".cursor"
            dest = dest_dir / "hooks" / "pretooluse_write_guard.json"
        elif args.target == "antigravity":
            dest_dir = ws / ".antigravity"
            dest = dest_dir / "hooks" / "pretooluse_write_guard.json"
        else:
            dest_dir = ws / ".godkiller"
            dest = dest_dir / "pretooluse_write_guard.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not args.force:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "reason": f"exists: {dest} (pass --force)",
                        "hint": "godkiller-write-guard install-hint",
                    }
                )
            )
            return 1
        shutil.copy2(pkg_hook, dest)
        marker = mark_write_guard_wired(source=f"install:{args.target}")
        print(
            json.dumps(
                {
                    "ok": True,
                    "copied": str(dest),
                    "marker": str(marker),
                    "next": (
                        "Wire host PreToolUse to: godkiller-write-guard --stdin. "
                        "Copying JSON is not enforcement proof."
                    ),
                },
                indent=2,
            )
        )
        return 0

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
