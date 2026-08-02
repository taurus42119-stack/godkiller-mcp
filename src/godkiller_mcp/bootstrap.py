"""Bootstrap a project for GODKILLER host write-guard + constitution.

Portable: no machine-specific absolute paths in generated files.
Honest: copying hooks is not proof the IDE fires PreToolUse.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

WRITE_MATCHER = "Write|Edit|NotebookEdit"
HOOK_CMD_WIN = "cmd /c .agents\\hooks\\godkiller-write-guard.cmd"
HOOK_CMD_POSIX = "sh .agents/hooks/godkiller-write-guard.sh"
HOOK_TIMEOUT = 15

_WIN_WRAPPER = """@echo off
setlocal EnableDelayedExpansion
REM GODKILLER write-guard — portable PreToolUse wrapper (no machine-specific paths)
REM Optional machine pin (gitignored): godkiller-write-guard.local.cmd
if exist "%~dp0godkiller-write-guard.local.cmd" (
  call "%~dp0godkiller-write-guard.local.cmd"
  exit /b !ERRORLEVEL!
)
where godkiller-write-guard >nul 2>&1
if !ERRORLEVEL!==0 (
  godkiller-write-guard --stdin
  exit /b !ERRORLEVEL!
)
where py >nul 2>&1
if !ERRORLEVEL!==0 (
  py -3 -m godkiller_mcp.write_guard --stdin
  exit /b !ERRORLEVEL!
)
where python >nul 2>&1
if !ERRORLEVEL!==0 (
  python -m godkiller_mcp.write_guard --stdin
  exit /b !ERRORLEVEL!
)
where python3 >nul 2>&1
if !ERRORLEVEL!==0 (
  python3 -m godkiller_mcp.write_guard --stdin
  exit /b !ERRORLEVEL!
)
echo GODKILLER write-guard: run godkiller-bootstrap again, or put Python/Scripts on PATH. 1>&2
exit /b 2
"""

_POSIX_WRAPPER = """#!/usr/bin/env sh
# GODKILLER write-guard — portable PreToolUse wrapper (no machine-specific paths)
# Optional machine pin (gitignored): godkiller-write-guard.local.sh
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$DIR/godkiller-write-guard.local.sh" ]; then
  exec sh "$DIR/godkiller-write-guard.local.sh"
fi
if command -v godkiller-write-guard >/dev/null 2>&1; then
  exec godkiller-write-guard --stdin
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 -m godkiller_mcp.write_guard --stdin
fi
if command -v python >/dev/null 2>&1; then
  exec python -m godkiller_mcp.write_guard --stdin
fi
echo "GODKILLER write-guard: run godkiller-bootstrap again, or put python3 on PATH." 1>&2
exit 2
"""

_HOOKS_GITIGNORE = """# Machine-local interpreter pin from godkiller-bootstrap — do not commit
godkiller-write-guard.local.cmd
godkiller-write-guard.local.sh
"""



def _pkg_root() -> Path:
    return Path(__file__).resolve().parent


def _bundled_agents_md() -> Path:
    return _pkg_root() / "bundled_agents" / "AGENTS.md"


def _bundled_prompts_md() -> Path:
    return _pkg_root() / "bundled_agents" / "PROMPTS.md"


def _bundled_hook_template() -> Path:
    p = _pkg_root() / "hooks" / "antigravity_pretooluse_write_guard.json"
    if p.is_file():
        return p
    return _pkg_root() / "hooks" / "pretooluse_write_guard.json"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def _load_hooks(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {
            "$schema": "https://ag-kit.dev/schemas/antigravity-hooks.schema.json",
            "enabled": True,
            "PreToolUse": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("$schema", "https://ag-kit.dev/schemas/antigravity-hooks.schema.json")
    data["enabled"] = True if data.get("enabled") is None else bool(data.get("enabled"))
    pre = data.get("PreToolUse")
    if not isinstance(pre, list):
        data["PreToolUse"] = []
    return data


def _is_write_guard_entry(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    matcher = str(entry.get("matcher") or "")
    command = str(entry.get("command") or "")
    if "Write" in matcher and "Edit" in matcher:
        return True
    return "write-guard" in command.lower() or "write_guard" in command.lower()


def merge_write_guard_hook(hooks: Dict[str, Any], *, windows: bool) -> Dict[str, Any]:
    """Insert or replace Write|Edit PreToolUse entry; keep unrelated hooks."""
    pre: List[Any] = list(hooks.get("PreToolUse") or [])
    kept = [e for e in pre if not _is_write_guard_entry(e)]
    entry = {
        "matcher": WRITE_MATCHER,
        "command": HOOK_CMD_WIN if windows else HOOK_CMD_POSIX,
        "timeout": HOOK_TIMEOUT,
    }
    kept.append(entry)
    hooks["PreToolUse"] = kept
    hooks["enabled"] = True
    return hooks


def bootstrap_workspace(
    workspace: Path,
    *,
    force_agents_md: bool = False,
    windows: Optional[bool] = None,
) -> Dict[str, Any]:
    """Materialize .agents constitution + portable write-guard hooks."""
    ws = workspace.resolve()
    if windows is None:
        windows = os.name == "nt"

    agents_md_src = _bundled_agents_md()
    hook_tpl = _bundled_hook_template()
    if not agents_md_src.is_file():
        return {"ok": False, "reason": f"missing bundled AGENTS.md: {agents_md_src}"}
    if not hook_tpl.is_file():
        return {"ok": False, "reason": f"missing hook template: {hook_tpl}"}

    agents_dir = ws / ".agents"
    hooks_dir = agents_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    dest_agents = agents_dir / "AGENTS.md"
    agents_action = "kept"
    if force_agents_md or not dest_agents.is_file():
        shutil.copy2(agents_md_src, dest_agents)
        agents_action = "copied" if not force_agents_md else "replaced"

    dest_prompts = agents_dir / "PROMPTS.md"
    prompts_src = _bundled_prompts_md()
    prompts_action = "skipped"
    if prompts_src.is_file():
        if force_agents_md or not dest_prompts.is_file():
            shutil.copy2(prompts_src, dest_prompts)
            prompts_action = "copied" if not force_agents_md else "replaced"
        else:
            prompts_action = "kept"

    dest_tpl = hooks_dir / "godkiller-write-guard.hooks.json"
    shutil.copy2(hook_tpl, dest_tpl)

    wrapper = hooks_dir / ("godkiller-write-guard.cmd" if windows else "godkiller-write-guard.sh")
    _write_text(wrapper, _WIN_WRAPPER if windows else _POSIX_WRAPPER)
    if not windows:
        try:
            wrapper.chmod(wrapper.stat().st_mode | 0o111)
        except OSError:
            pass

    # Machine pin: absolute interpreter from this bootstrap run (gitignored).
    # Keeps portable wrapper free of personal paths for repo distribution.
    py_exe = Path(sys.executable).resolve()
    if windows:
        local_pin = hooks_dir / "godkiller-write-guard.local.cmd"
        _write_text(
            local_pin,
            (
                "@echo off\n"
                "REM Machine-local GODKILLER pin — gitignored; regenerate via godkiller-bootstrap\n"
                f'"{py_exe}" -m godkiller_mcp.write_guard --stdin\n'
                "exit /b %ERRORLEVEL%\n"
            ),
        )
    else:
        local_pin = hooks_dir / "godkiller-write-guard.local.sh"
        _write_text(
            local_pin,
            (
                "#!/usr/bin/env sh\n"
                "# Machine-local GODKILLER pin — gitignored; regenerate via godkiller-bootstrap\n"
                f'exec "{py_exe}" -m godkiller_mcp.write_guard --stdin\n'
            ),
        )
        try:
            local_pin.chmod(local_pin.stat().st_mode | 0o111)
        except OSError:
            pass

    gi = hooks_dir / ".gitignore"
    if not gi.is_file() or "godkiller-write-guard.local" not in gi.read_text(encoding="utf-8", errors="ignore"):
        _write_text(gi, _HOOKS_GITIGNORE)

    hooks_path = agents_dir / "hooks.json"
    hooks = merge_write_guard_hook(_load_hooks(hooks_path), windows=windows)
    hooks_path.write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8")

    from godkiller_mcp.write_guard import mark_write_guard_wired

    marker = mark_write_guard_wired(source="bootstrap")

    return {
        "ok": True,
        "workspace": str(ws),
        "agents_md": str(dest_agents),
        "agents_md_action": agents_action,
        "prompts_md": str(dest_prompts) if prompts_src.is_file() else None,
        "prompts_md_action": prompts_action,
        "hooks_json": str(hooks_path),
        "wrapper": str(wrapper),
        "local_pin": str(local_pin),
        "local_pin_note": (
            "local_pin uses this machine's Python and must stay gitignored "
            "(.agents/hooks/.gitignore). Commit only the portable wrapper + hooks.json."
        ),
        "template": str(dest_tpl),
        "marker": str(marker),
        "hook_command": HOOK_CMD_WIN if windows else HOOK_CMD_POSIX,
        "honest": (
            "Bootstrap wrote portable .agents files + a gitignored local interpreter pin. "
            "Reload the IDE. Native Write stays free until the host fires PreToolUse. "
            "Do not set GODKILLER_WRITE_GUARD_PROVEN=1 until a live deny/allow test passes."
        ),
        "next": [
            "Reload the IDE on this workspace.",
            "Prove: deny path outside allowlist; allow after gk_guard.set_paths / persist_allow_paths.",
            "Only then set GODKILLER_WRITE_GUARD_PROVEN=1 for ship posture.",
            "Do not commit godkiller-write-guard.local.cmd / .local.sh (personal paths).",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap .agents AGENTS.md + portable write-guard hooks for a workspace"
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--force-agents-md",
        action="store_true",
        help="Overwrite existing .agents/AGENTS.md with the shipped constitution",
    )
    parser.add_argument(
        "--posix",
        action="store_true",
        help="Force POSIX wrapper/hook command (default: auto by OS)",
    )
    parser.add_argument(
        "--windows",
        action="store_true",
        help="Force Windows wrapper/hook command",
    )
    args = parser.parse_args(argv)

    if args.posix and args.windows:
        print(json.dumps({"ok": False, "reason": "pass only one of --posix / --windows"}))
        return 2

    windows: Optional[bool]
    if args.windows:
        windows = True
    elif args.posix:
        windows = False
    else:
        windows = None

    ws = Path(args.workspace or os.getcwd()).resolve()
    result = bootstrap_workspace(ws, force_agents_md=args.force_agents_md, windows=windows)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
