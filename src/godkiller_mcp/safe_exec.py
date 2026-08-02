"""Run verification commands without a shell — never shell=True (RCE surface)."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence

# Never leak host secrets into pytest/verify/soak children (forge write_allow chain).
_SCRUB_ENV_EXACT = frozenset(
    {
        "GODKILLER_SEAL_KEY",
        "GODKILLER_LLM_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "NPM_TOKEN",
        "TWINE_PASSWORD",
    }
)


def scrubbed_environ(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Copy env with seal/API secrets removed for child processes."""
    env = dict(base if base is not None else os.environ)
    for key in list(env.keys()):
        upper = key.upper()
        if upper in _SCRUB_ENV_EXACT:
            env.pop(key, None)
            continue
        if upper.endswith("_SEAL_KEY") or upper.endswith("_SECRET_KEY"):
            env.pop(key, None)
            continue
        if "SEAL_KEY" in upper and upper.startswith("GODKILLER_"):
            env.pop(key, None)
    return env


def split_command(command: str) -> List[str]:
    """Split a command string into argv without invoking a shell."""
    try:
        return shlex.split(command, posix=os_name_is_posix())
    except ValueError:
        return command.strip().split()


def os_name_is_posix() -> bool:
    return os.name != "nt"


def run_command_safely(
    command: str | Sequence[str],
    *,
    cwd: str | Path,
    timeout_sec: int = 30,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    """
    Always argv + shell=False.
    Child env is scrubbed of GODKILLER_SEAL_KEY / API secrets by default.
    FileNotFoundError is fail-closed (no Windows shell=True fallback — that was RCE).
    """
    raw_for_check = command if isinstance(command, str) else " ".join(str(x) for x in command)
    if any(c in raw_for_check for c in (";", "&", "|", "`", "$", "\n", "\r")):
        raise ValueError("Shell metacharacters are not allowed in safe_exec argv")

    if isinstance(command, str):
        argv = split_command(command)
    else:
        argv = [str(x) for x in command]

    if not argv:
        raise ValueError("Empty command")

    # Defense in depth: refuse shell metacharacters even in argv form
    joined = " ".join(argv)
    if any(c in joined for c in (";", "&", "|", "`", "$", "\n", "\r")):
        raise ValueError("Shell metacharacters are not allowed in safe_exec argv")

    work_dir = Path(cwd)
    child_env = scrubbed_environ(env)
    try:
        return subprocess.run(
            argv,
            shell=False,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=child_env,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Executable not found for argv={argv!r} (cwd={work_dir}). "
            "GODKILLER refuses shell=True fallback — install the tool on PATH "
            "or use an allowlisted python -m form."
        ) from exc
