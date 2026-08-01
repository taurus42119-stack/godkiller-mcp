"""Cross-platform advisory file lock for .godkiller state files.

Not a distributed lock — only serializes processes sharing one workspace path.
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional


@contextmanager
def workspace_lock(
    workspace: Path | str,
    *,
    name: str = "state.lock",
    timeout_sec: float = 30.0,
) -> Iterator[Path]:
    """Acquire an exclusive lock under ``<workspace>/.godkiller/<name>``."""
    ws = Path(workspace).resolve()
    root = ws / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / name
    lock_path.touch(exist_ok=True)
    fh = open(lock_path, "a+b")
    deadline = time.monotonic() + max(0.1, float(timeout_sec))
    locked = False
    try:
        while True:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"workspace_lock timeout waiting for {lock_path} "
                        f"(another process holds .godkiller/{name})"
                    )
                time.sleep(0.05)
        yield lock_path
    finally:
        if locked:
            try:
                if sys.platform == "win32":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        fh.close()


def try_warn_stderr(msg: str) -> None:
    try:
        print(msg, file=sys.stderr, flush=True)
    except OSError:
        pass
