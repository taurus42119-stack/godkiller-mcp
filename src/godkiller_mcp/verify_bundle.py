"""Verify bundle runner and command allowlist."""

from __future__ import annotations

import hashlib
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from godkiller_mcp.safe_exec import run_command_safely
from godkiller_mcp.schema import TaskState

# Kernel verify: only these command shapes are accepted.
_ALLOWED_PREFIXES = (
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("py", "-m", "pytest"),
    ("pytest",),
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
    ("ruff",),
    ("mypy",),
)

_FORBIDDEN_META = re.compile(r"[;&|`$]|&&|\|\|")


def _split(command: str) -> List[str]:
    try:
        import os

        return shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return command.strip().split()


def detect_hacking(command: str) -> Tuple[bool, str]:
    """Return (blocked, reason). Prefer allowlist over silly substring bans."""
    if not command or not command.strip():
        return True, "Empty verify command"
    if _FORBIDDEN_META.search(command):
        return True, "Shell metacharacters are not allowed in verify commands"
    argv = _split(command)
    if not argv:
        return True, "Empty verify command"
    lower = [a.lower() for a in argv]
    for prefix in _ALLOWED_PREFIXES:
        plen = len(prefix)
        if lower[:plen] == list(prefix):
            return False, ""
    return (
        True,
        "Command not on verify allowlist "
        "(allowed: pytest / python -m pytest|unittest / ruff / mypy)",
    )


@dataclass
class VerifyResult:
    passed: bool
    hack_blocked: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    reason: str = ""
    command_fingerprint: str = ""
    cwd: str = ""
    result_digest: str = ""

    @property
    def summary(self) -> str:
        if self.hack_blocked:
            return f"verify_bundle BLOCKED: {self.reason}"
        if self.passed:
            return "verify_bundle PASS"
        return f"verify_bundle FAIL: {self.reason or self.stderr[:200]}"

    def compute_digest(self) -> str:
        material = "|".join(
            [
                self.command_fingerprint,
                str(self.exit_code),
                "1" if self.passed else "0",
                self.stdout[-8000:],
                self.stderr[-4000:],
                self.cwd,
            ]
        )
        return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()

    def to_payload(self) -> dict:
        digest = self.result_digest or self.compute_digest()
        return {
            "source": "verify_bundle",
            "server_authored": True,
            "passed": self.passed,
            "hack_blocked": self.hack_blocked,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-4000:],
            "stderr": self.stderr[-4000:],
            "reason": self.reason,
            "summary": self.summary,
            "command_fingerprint": self.command_fingerprint,
            "cwd": self.cwd,
            "result_digest": digest,
        }


def task_has_passing_verify_bundle(state: TaskState) -> Tuple[bool, str]:
    for ev in state.evidences:
        payload = ev.payload or {}
        if (
            payload.get("source") == "verify_bundle"
            and payload.get("passed")
            and payload.get("server_authored") is True
        ):
            if not payload.get("result_digest"):
                return (
                    False,
                    "verify_bundle evidence missing result_digest — rerun verify_bundle on this build",
                )
            return True, "verify_bundle passed"
    return False, "verify_bundle evidence missing, failed, or not server-authored"


class VerifyBundleRunner:
    def __init__(self, timeout_sec: int = 30):
        self.timeout_sec = timeout_sec

    def run(self, cwd: str | Path, commands: List[str] | None = None) -> VerifyResult:
        work_dir = Path(cwd).resolve()
        if not commands:
            commands = ["python -m pytest -q"]

        fingerprints = []
        last_stdout = ""
        last_stderr = ""

        for cmd in commands:
            is_hack, reason = detect_hacking(cmd)
            fp = hashlib.sha256(cmd.encode("utf-8")).hexdigest()[:16]
            fingerprints.append(fp)
            if is_hack:
                return VerifyResult(
                    passed=False,
                    hack_blocked=True,
                    exit_code=1,
                    reason=reason,
                    command_fingerprint=",".join(fingerprints),
                    cwd=str(work_dir),
                )

            try:
                proc = run_command_safely(
                    cmd,
                    cwd=work_dir,
                    timeout_sec=self.timeout_sec,
                )
                last_stdout = proc.stdout or ""
                last_stderr = proc.stderr or ""
                if proc.returncode != 0:
                    return VerifyResult(
                        passed=False,
                        hack_blocked=False,
                        exit_code=proc.returncode,
                        stdout=last_stdout,
                        stderr=last_stderr,
                        reason=f"Command '{cmd}' failed with exit code {proc.returncode}",
                        command_fingerprint=",".join(fingerprints),
                        cwd=str(work_dir),
                    )
            except Exception as e:
                return VerifyResult(
                    passed=False,
                    hack_blocked=False,
                    exit_code=1,
                    reason=str(e),
                    command_fingerprint=",".join(fingerprints),
                    cwd=str(work_dir),
                )

        return VerifyResult(
            passed=True,
            hack_blocked=False,
            exit_code=0,
            stdout=last_stdout or "All verification commands passed cleanly",
            stderr=last_stderr,
            command_fingerprint=",".join(fingerprints),
            cwd=str(work_dir),
            result_digest="",
        )
