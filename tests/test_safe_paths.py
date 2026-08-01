"""Guard against shipping machine-specific absolute user paths."""

from __future__ import annotations

import re
from pathlib import Path

from godkiller_mcp.code_intel import _default_tools_dir
from godkiller_mcp.safe_exec import split_command
from godkiller_mcp.verify_bundle import VerifyBundleRunner

_REPO_ROOT = Path(__file__).resolve().parents[1]

_SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "arena_logs",
    "logs",
    "_vendor_study",
    "docs",
    "_recover_writes",
}

_SCAN_SUFFIXES = {".py", ".md", ".ps1", ".json", ".toml", ".yml", ".yaml", ".txt", ".sh"}

# Generic home-dir absolute paths (no real developer usernames in this file).
_HOME_PATH_RE = re.compile(
    r"(?i)(?:C:\\Users\\|C:/Users/|/Users/|/home/)"
    r"(?!Public\b|Shared\b|Default\b|All\sUsers\b|"
    r"<|YOUR_|\$|%USERPROFILE%|~|"
    r"me\b|you\b|user\b|username\b|alice\b|bob\b|example\b)"
    r"[A-Za-z0-9._-]+"
)


def _iter_ship_files():
    for path in _REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in _SCAN_SUFFIXES and path.name not in (
            "Dockerfile",
            "Makefile",
        ):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        yield path


def test_no_hardcoded_user_home_paths_in_repo():
    assert _default_tools_dir() is None or "Users" not in str(_default_tools_dir())
    leaks: list[str] = []
    for path in _iter_ship_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in _HOME_PATH_RE.finditer(text):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            leaks.append(f"{rel}: {m.group(0)!r}")
            break
    assert not leaks, "machine-specific home path leaks:\n" + "\n".join(leaks)


def test_state_root_defaults_to_home(monkeypatch, tmp_path):
    from godkiller_mcp.runtime_paths import resolve_state_root

    monkeypatch.delenv("GODKILLER_HOME", raising=False)
    home = tmp_path / "homeuser"
    home.mkdir()
    monkeypatch.setattr(
        "godkiller_mcp.runtime_paths.Path.home",
        lambda: home,
    )
    root = resolve_state_root()
    assert root == (home / ".godkiller").resolve()
    assert root.is_dir()


def test_split_command_basic():
    assert split_command("python -m pytest -q")[:3] == ["python", "-m", "pytest"]


def test_verify_runner_blocks_todo_echo(tmp_path):
    runner = VerifyBundleRunner(timeout_sec=5)
    result = runner.run(tmp_path, ["echo TODO"])
    assert result.passed is False
    assert result.hack_blocked is True
