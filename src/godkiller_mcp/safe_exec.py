"""Run verification commands without shell=True when possible."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import List, Sequence, Tuple


def split_command(command: str) -> List[str]:
    """Split a command string into argv without invoking a shell."""
    try:
        return shlex.split(command, posix=os_name_is_posix())
    except ValueError:
        # Unbalanced quotes — fall back to naive split
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
    Prefer argv list + shell=False.
    On Windows, allow shell=True only for builtins that have no .exe (e.g. `dir`),
    but never for empty/whitespace commands.
    """
    if isinstance(command, str):
        argv = split_command(command)
    else:
        argv = [str(x) for x in command]

    if not argv:
        raise ValueError("Empty command")

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
    except FileNotFoundError:
        # Windows builtins / PATH edge cases: last-resort shell, still with argv[0] only if needed
        import os

        if os.name == "nt" and isinstance(command, str):
            return subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
        raise
