"""Verify bundle runner and command allowlist."""

from __future__ import annotations

import hashlib
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from godkiller_mcp.safe_exec import run_command_safely
from godkiller_mcp.schema import EvidenceType, TaskState

# Kernel verify: only these command shapes are accepted.
_TEST_PREFIXES = (
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("py", "-m", "pytest"),
    ("pytest",),
    ("python", "-m", "unittest"),
    ("python3", "-m", "unittest"),
)
_LINT_PREFIXES = (
    ("ruff",),
    ("mypy",),
)
_ALLOWED_PREFIXES = _TEST_PREFIXES + _LINT_PREFIXES

# Markers that suggest a non-Python project — kernel claim-grade verify is Python-only.
_NON_PYTHON_MARKERS = (
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
)


def detect_non_python_project(cwd: str | Path) -> List[str]:
    """Return marker filenames present that imply Node/Go/etc. (not claim-grade here)."""
    root = Path(cwd)
    found: List[str] = []
    for name in _NON_PYTHON_MARKERS:
        if (root / name).is_file():
            found.append(name)
    return found


def non_python_verify_warning(cwd: str | Path) -> str:
    found = detect_non_python_project(cwd)
    if not found:
        return ""
    return (
        "non_python_project_markers="
        + ",".join(found)
        + " — kernel claim-grade verify_bundle is Python "
        "(pytest/unittest/ruff/mypy) only; use a host/CI oracle for JS/TS/Go/etc."
    )


def is_test_verify_command(command_or_fp: str) -> bool:
    """True if fingerprint/command is pytest/unittest (not lint-only)."""
    if not command_or_fp:
        return False
    # fingerprints may be joined with || for multi-command
    chunks = [c.strip() for c in command_or_fp.replace("||", "\n").split("\n") if c.strip()]
    if not chunks and command_or_fp.strip():
        chunks = [command_or_fp.strip()]
    for chunk in chunks:
        argv = _split(chunk)
        if not argv:
            continue
        lower = [a.lower() for a in argv]
        for prefix in _TEST_PREFIXES:
            plen = len(prefix)
            if lower[:plen] == list(prefix):
                return True
    return False


_FORBIDDEN_META = re.compile(r"[;&|`$]|&&|\|\|")

# Pytest flags that can escape the workspace / inject config (critic: shallow allowlist).
_PYTEST_DENY_FLAGS = {
    "-c",
    "--override-ini",
    "-p",
    "--pyargs",
    "--confcutdir",
    "--rootdir",
    "--basetemp",
}


def _split(command: str) -> List[str]:
    try:
        import os

        return shlex.split(command, posix=(os.name != "nt"))
    except ValueError:
        return command.strip().split()


def _pytest_argv_denied(argv: List[str]) -> Tuple[bool, str]:
    """Block dangerous pytest argv even when prefix allowlist matches."""
    lower = [a.lower() for a in argv]
    # Find pytest entry
    start = 0
    if lower[:3] in (["python", "-m", "pytest"], ["python3", "-m", "pytest"], ["py", "-m", "pytest"]):
        start = 3
    elif lower[:1] == ["pytest"]:
        start = 1
    else:
        return False, ""
    rest = argv[start:]
    i = 0
    while i < len(rest):
        tok = rest[i]
        key = tok.split("=", 1)[0].lower() if tok.startswith("-") else tok.lower()
        # -cCONFIG / -c CONFIG / --override-ini=... / -p no:x
        if key in _PYTEST_DENY_FLAGS or any(
            key.startswith(f"{d}=") for d in _PYTEST_DENY_FLAGS if d.startswith("--")
        ):
            return True, f"verify deny-list: pytest flag `{tok}` not allowed (workspace escape / config inject)"
        # short -c without space already covered; -c value as next arg
        if tok in ("-c", "-p") or tok.lower() in (
            "--override-ini",
            "--pyargs",
            "--confcutdir",
            "--rootdir",
            "--basetemp",
        ):
            return True, f"verify deny-list: pytest flag `{tok}` not allowed"
        i += 1
    return False, ""


def _tool_paths_outside_workspace(argv: List[str], work_dir: Path) -> Tuple[bool, str]:
    """Deny absolute / .. path args that escape work_dir (pytest/unittest/ruff/mypy)."""
    lower = [a.lower() for a in argv]
    start = 0
    if lower[:3] in (["python", "-m", "pytest"], ["python3", "-m", "pytest"], ["py", "-m", "pytest"]):
        start = 3
    elif lower[:1] == ["pytest"]:
        start = 1
    elif lower[:3] in (["python", "-m", "unittest"], ["python3", "-m", "unittest"]):
        start = 3
    elif lower[:1] == ["ruff"]:
        start = 1
        if len(lower) > 1 and lower[1] in (
            "check",
            "format",
            "rule",
            "linter",
            "analyze",
            "clean",
        ):
            start = 2
    elif lower[:1] == ["mypy"]:
        start = 1
    else:
        return False, ""
    root = work_dir.resolve()
    i = start
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-"):
            # skip flag values that are not paths we care about
            if tok in ("-k", "-m", "--maxfail", "-n", "--select", "--ignore") and i + 1 < len(
                argv
            ):
                i += 2
                continue
            i += 1
            continue
        # positional path-like
        if "/" in tok or "\\" in tok or tok.endswith((".py", ".txt", ".toml")) or tok.startswith(
            ("tests", "src", ".")
        ):
            p = Path(tok)
            candidate = p if p.is_absolute() else (root / p)
            try:
                resolved = candidate.resolve()
                resolved.relative_to(root)
            except (OSError, ValueError):
                return True, f"verify deny: path escapes workspace: {tok}"
            if ".." in Path(tok).parts:
                try:
                    (root / tok).resolve().relative_to(root)
                except (OSError, ValueError):
                    return True, f"verify deny: path escapes workspace: {tok}"
        i += 1
    return False, ""


def detect_hacking(command: str, *, cwd: str | Path | None = None) -> Tuple[bool, str]:
    """Return (blocked, reason). Prefer allowlist matching over substring heuristics."""
    if not command or not command.strip():
        return True, "Empty verify command"
    if _FORBIDDEN_META.search(command):
        return True, "Shell metacharacters are not allowed in verify commands"
    argv = _split(command)
    if not argv:
        return True, "Empty verify command"
    lower = [a.lower() for a in argv]
    matched = False
    for prefix in _ALLOWED_PREFIXES:
        plen = len(prefix)
        if lower[:plen] == list(prefix):
            matched = True
            break
    if not matched:
        return (
            True,
            "Command not on verify allowlist "
            "(allowed: pytest / python -m pytest|unittest / ruff / mypy)",
        )
    denied, reason = _pytest_argv_denied(argv)
    if denied:
        return True, reason
    if cwd is not None:
        outside, why = _tool_paths_outside_workspace(argv, Path(cwd))
        if outside:
            return True, why
    return False, ""


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
    commands: List[str] | None = None
    is_test_suite: bool = False
    warnings: List[str] = field(default_factory=list)
    host_oracle_hint: str = ""

    @property
    def summary(self) -> str:
        if self.hack_blocked:
            return f"verify_bundle BLOCKED: {self.reason}"
        if self.passed:
            kind = "TEST" if self.is_test_suite else "LINT"
            base = f"verify_bundle PASS ({kind})"
            if self.warnings:
                return base + " WARN: " + "; ".join(self.warnings[:2])
            return base
        return f"verify_bundle FAIL: {self.reason or self.stderr[:200]}"

    def compute_digest(self) -> str:
        material = "|".join(
            [
                self.command_fingerprint,
                str(self.exit_code),
                "1" if self.passed else "0",
                "T" if self.is_test_suite else "L",
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
            "commands": list(self.commands or []),
            "is_test_suite": self.is_test_suite,
            "cwd": self.cwd,
            "result_digest": digest,
            "warnings": list(self.warnings or []),
            "host_oracle_hint": self.host_oracle_hint,
            "claim_grade_scope": "python_pytest_unittest_ruff_mypy",
        }


def task_has_passing_verify_bundle(state: TaskState) -> Tuple[bool, str]:
    from godkiller_mcp.freshness import evidence_fresh_against_disk

    saw_lint_only = False
    for ev in state.evidences:
        payload = ev.payload or {}
        if (
            payload.get("source") != "verify_bundle"
            or not payload.get("passed")
            or payload.get("server_authored") is not True
        ):
            continue
        # Claim-grade: must be PASSING_TEST from a real test runner — not LOG, not lint-only
        if ev.type != EvidenceType.PASSING_TEST:
            continue
        if payload.get("is_test_suite") is False:
            saw_lint_only = True
            continue
        cmds = payload.get("commands") or []
        if cmds and not any(is_test_verify_command(str(c)) for c in cmds):
            saw_lint_only = True
            continue
        if not payload.get("result_digest"):
            return (
                False,
                "verify_bundle evidence missing result_digest — rerun verify_bundle on this build",
            )
        ok_f, reason_f = evidence_fresh_against_disk(
            payload,
            workspace=payload.get("cwd"),
            state=state,
        )
        if not ok_f:
            return False, reason_f
        return True, "verify_bundle passed (fresh)"
    if saw_lint_only:
        return (
            False,
            "verify_bundle lint/mypy alone is not claim-grade — run pytest/unittest via verify_bundle",
        )
    return False, "verify_bundle evidence missing, failed, or not server-authored"


class VerifyBundleRunner:
    def __init__(self, timeout_sec: int = 30):
        self.timeout_sec = timeout_sec

    def run(self, cwd: str | Path, commands: List[str] | None = None) -> VerifyResult:
        work_dir = Path(cwd).resolve()
        if not commands:
            commands = ["python -m pytest -q"]
        is_test_suite = any(is_test_verify_command(c) for c in commands)
        lang_warn = non_python_verify_warning(work_dir)
        warnings = [lang_warn] if lang_warn else []
        host_hint = (
            "Run project-native tests on the host (npm test / go test / cargo test) "
            "and attach results outside claim-grade verify_bundle."
            if lang_warn
            else ""
        )

        fingerprints = []
        last_stdout = ""
        last_stderr = ""

        for cmd in commands:
            is_hack, reason = detect_hacking(cmd, cwd=work_dir)
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
                    commands=list(commands),
                    is_test_suite=is_test_suite,
                    warnings=list(warnings),
                    host_oracle_hint=host_hint,
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
                        commands=list(commands),
                        is_test_suite=is_test_suite,
                        warnings=list(warnings),
                        host_oracle_hint=host_hint,
                    )
            except Exception as e:
                return VerifyResult(
                    passed=False,
                    hack_blocked=False,
                    exit_code=1,
                    reason=str(e),
                    command_fingerprint=",".join(fingerprints),
                    cwd=str(work_dir),
                    commands=list(commands),
                    is_test_suite=is_test_suite,
                    warnings=list(warnings),
                    host_oracle_hint=host_hint,
                )

        out = VerifyResult(
            passed=True,
            hack_blocked=False,
            exit_code=0,
            stdout=last_stdout,
            stderr=last_stderr,
            command_fingerprint=",".join(fingerprints),
            cwd=str(work_dir),
            commands=list(commands),
            is_test_suite=is_test_suite,
            warnings=list(warnings),
            host_oracle_hint=host_hint,
        )
        out.result_digest = out.compute_digest()
        return out
