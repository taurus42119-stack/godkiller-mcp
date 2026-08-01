"""Guard against shipping machine-specific absolute user paths."""

from __future__ import annotations

from pathlib import Path

from godkiller_mcp.code_intel import _default_tools_dir
from godkiller_mcp.safe_exec import split_command
from godkiller_mcp.verify_bundle import VerifyBundleRunner

# Package root = parents of tests/
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
    "arena_logs",  # local score receipts (gitignored)
    "logs",
}

_SCAN_SUFFIXES = {".py", ".md", ".ps1", ".json", ".toml", ".yml", ".yaml", ".txt", ".sh"}

# Hardcoded personal Windows profiles must never ship.
_FORBIDDEN_SNIPPETS = (
    r"C:\Users\ASUS",
    "C:/Users/ASUS",
    r"C:\\Users\\ASUS",
    "/Users/ASUS",
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
        # Allow this test file to mention the forbidden strings as needles.
        if path.resolve() == Path(__file__).resolve():
            continue
        yield path


def test_no_hardcoded_asus_paths_in_repo():
    assert _default_tools_dir() is None or "ASUS" not in str(_default_tools_dir())
    leaks: list[str] = []
    for path in _iter_ship_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in _FORBIDDEN_SNIPPETS:
            if needle in text:
                rel = path.relative_to(_REPO_ROOT).as_posix()
                leaks.append(f"{rel}: contains {needle!r}")
                break
    assert not leaks, "machine-specific path leaks:\n" + "\n".join(leaks)


def test_state_root_defaults_to_home(monkeypatch, tmp_path):
    from godkiller_mcp.runtime_paths import resolve_state_root

    monkeypatch.delenv("GODKILLER_HOME", raising=False)
    monkeypatch.setattr(
        "godkiller_mcp.runtime_paths.Path.home",
        lambda: tmp_path / "homeuser",
    )
    root = resolve_state_root()
    assert root == (tmp_path / "homeuser" / ".godkiller").resolve()
    assert root.is_dir()


def test_split_command_basic():
    assert split_command("python -m pytest -q")[:3] == ["python", "-m", "pytest"]


def test_verify_runner_blocks_todo_echo(tmp_path):
    runner = VerifyBundleRunner(timeout_sec=5)
    result = runner.run(tmp_path, ["echo TODO"])
    assert result.passed is False
    assert result.hack_blocked is True
