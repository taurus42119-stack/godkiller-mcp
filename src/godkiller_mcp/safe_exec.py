"""Run verification commands without a shell — never shell=True (RCE surface)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List, Sequence


def split_command(command: str) -> List[str]:
    """Split a command string into argv without invoking a shell."""
    try:
        return shlex.split(command, posix=os_name_is_posix())
    except ValueError:
        return command.strip().split()


def os_name_is_posix() -> bool:
    import os

    return os.name != "nt"


def run_command_safely(
    command: str | Sequence[str],
    *,
    cwd: str | Path,
    timeout_sec: int = 30,
) -> subprocess.CompletedProcess[str]:
    """
    Always argv + shell=False.
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
    try:
        return subprocess.run(
            argv,
            shell=False,
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Executable not found for argv={argv!r} (cwd={work_dir}). "
            "GODKILLER refuses shell=True fallback — install the tool on PATH "
            "or use an allowlisted python -m form."
        ) from exc
