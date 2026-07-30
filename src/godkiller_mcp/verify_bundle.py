"""Verify bundle runner and command safety detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from godkiller_mcp.safe_exec import run_command_safely
from godkiller_mcp.schema import TaskState


def detect_hacking(command: str) -> Tuple[bool, str]:
    forbidden_patterns = [
        "echo ok",
        "rm -rf /",
        "format c:",
        "> /dev/null",
        "TODO",
    ]
    for pattern in forbidden_patterns:
        if pattern in command:
            return True, f"Blocked forbidden pattern: '{pattern}' in command"
    return False, ""


def task_has_passing_verify_bundle(state: TaskState) -> Tuple[bool, str]:
    for ev in state.evidences:
        payload = ev.payload or {}
        if payload.get("source") == "verify_bundle" and payload.get("passed"):
            return True, "verify_bundle passed"
    return False, "verify_bundle evidence missing or failed"


@dataclass
class VerifyResult:
    passed: bool
    hack_blocked: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    reason: str = ""

    @property
    def summary(self) -> str:
        if self.hack_blocked:
            return f"verify_bundle BLOCKED: {self.reason}"
        if self.passed:
            return "verify_bundle PASS"
        return f"verify_bundle FAIL: {self.reason or self.stderr[:200]}"

    def to_payload(self) -> dict:
        return {
            "source": "verify_bundle",
            "passed": self.passed,
            "hack_blocked": self.hack_blocked,
            "exit_code": self.exit_code,
            "stdout": self.stdout[-4000:],
            "stderr": self.stderr[-4000:],
            "reason": self.reason,
            "summary": self.summary,
        }


class VerifyBundleRunner:
    def __init__(self, timeout_sec: int = 30):
        self.timeout_sec = timeout_sec

    def run(self, cwd: str | Path, commands: List[str] | None = None) -> VerifyResult:
        work_dir = Path(cwd)
        if not commands:
            commands = ["python -m pytest -q"]

        for cmd in commands:
            is_hack, reason = detect_hacking(cmd)
            if is_hack:
                return VerifyResult(
                    passed=False,
                    hack_blocked=True,
                    exit_code=1,
                    reason=reason,
                )

            try:
                proc = run_command_safely(
                    cmd,
                    cwd=work_dir,
                    timeout_sec=self.timeout_sec,
                )
                if proc.returncode != 0:
                    return VerifyResult(
                        passed=False,
                        hack_blocked=False,
                        exit_code=proc.returncode,
                        stdout=proc.stdout,
                        stderr=proc.stderr,
                        reason=f"Command '{cmd}' failed with exit code {proc.returncode}",
                    )
            except Exception as e:
                return VerifyResult(
                    passed=False,
                    hack_blocked=False,
                    exit_code=1,
                    reason=str(e),
                )

        return VerifyResult(
            passed=True,
            hack_blocked=False,
            exit_code=0,
            stdout="All verification commands passed cleanly",
        )
