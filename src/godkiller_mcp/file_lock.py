"""Cross-platform advisory file lock for .godkiller state files.

Not a distributed lock — only serializes processes sharing one workspace path.
Stale locks: if the holder PID is dead (or meta is older than max_age), clear and retry.
"""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists but not signalable — treat as alive
        return True
    except OSError:
        return False


def _meta_path(lock_path: Path) -> Path:
    return lock_path.with_suffix(lock_path.suffix + ".meta")


def _write_lock_meta(lock_path: Path) -> None:
    meta = {"pid": os.getpid(), "ts": time.time()}
    try:
        _meta_path(lock_path).write_text(json.dumps(meta), encoding="utf-8")
    except OSError:
        pass


def _clear_stale_lock(lock_path: Path, *, max_age_sec: float = 3600.0) -> bool:
    """Return True if a dead/expired holder meta was cleared."""
    meta_file = _meta_path(lock_path)
    if not meta_file.is_file():
        return False
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        pid = int(meta.get("pid") or 0)
        ts = float(meta.get("ts") or 0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            meta_file.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    stale = (not _pid_alive(pid)) or (ts > 0 and (time.time() - ts) > max_age_sec)
    if not stale:
        return False
    try:
        meta_file.unlink(missing_ok=True)
    except OSError:
        pass
    return True


@contextmanager
def workspace_lock(
    workspace: Path | str,
    *,
    name: str = "state.lock",
    timeout_sec: float = 30.0,
    stale_max_age_sec: float = 3600.0,
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
    cleared_once = False
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
                _write_lock_meta(lock_path)
                break
            except OSError:
                if not cleared_once and _clear_stale_lock(
                    lock_path, max_age_sec=stale_max_age_sec
                ):
                    cleared_once = True
                    time.sleep(0.05)
                    continue
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
                _meta_path(lock_path).unlink(missing_ok=True)
            except OSError:
                pass
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


@contextmanager
def path_lock(
    lock_path: Path | str,
    *,
    timeout_sec: float = 30.0,
    stale_max_age_sec: float = 3600.0,
) -> Iterator[Path]:
    """Advisory exclusive lock on an arbitrary lock file path (tasks/evidence persist)."""
    lock_path = Path(lock_path).resolve()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    fh = open(lock_path, "a+b")
    deadline = time.monotonic() + max(0.1, float(timeout_sec))
    locked = False
    cleared_once = False
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
                _write_lock_meta(lock_path)
                break
            except OSError:
                if not cleared_once and _clear_stale_lock(
                    lock_path, max_age_sec=stale_max_age_sec
                ):
                    cleared_once = True
                    time.sleep(0.05)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"path_lock timeout waiting for {lock_path} "
                        "(another process may share GODKILLER_HOME — use one HOME per session)"
                    )
                time.sleep(0.05)
        yield lock_path
    finally:
        if locked:
            try:
                _meta_path(lock_path).unlink(missing_ok=True)
            except OSError:
                pass
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
