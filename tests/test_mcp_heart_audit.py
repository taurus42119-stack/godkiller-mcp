"""AST security scan, SQLite busy retry, SSRF schemes, safe_exec edges, tool hints."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from godkiller_mcp.code_intel import SecurityScanEngine
from godkiller_mcp.memory_lessons import LessonMemory, _with_busy_retry
from godkiller_mcp.safe_exec import run_command_safely, split_command
from godkiller_mcp.ssrf import assert_public_url
from godkiller_mcp.tool_hints import install_hint


def test_ast_scan_catches_eval_and_shell_true(tmp_path: Path):
    bad = tmp_path / "bad.py"
    bad.write_text(
        "x = eval('1')\n"
        "import subprocess\n"
        "subprocess.run(['echo', 'hi'], shell=True)\n"
        "# mention eval in a comment only\n",
        encoding="utf-8",
    )
    clean = tmp_path / "clean.py"
    clean.write_text("def ok():\n    return 1\n", encoding="utf-8")
    out = SecurityScanEngine().scan(str(tmp_path))
    assert out["engine"] == "python_ast_security"
    issues = " ".join(i["issue"] for i in out["issues"])
    assert "eval" in issues.lower()
    assert "shell=True" in issues
    # comment-only file should not create a lone comment hit as Call
    comment_only = tmp_path / "comment.py"
    comment_only.write_text("# never call eval here\n", encoding="utf-8")
    out2 = SecurityScanEngine().scan(str(comment_only.parent))
    # still may find bad.py; ensure comment-only line not listed as eval Call from comment.py
    for i in out2["issues"]:
        if i["file"].endswith("comment.py"):
            assert "eval" not in i["issue"].lower()


def test_ast_scan_comment_only_no_eval_issue(tmp_path: Path):
    p = tmp_path / "only_comment.py"
    p.write_text("# eval( is not a call\n", encoding="utf-8")
    out = SecurityScanEngine().scan(str(tmp_path))
    assert out["total_issues"] == 0


def test_sqlite_busy_retry_succeeds(tmp_path: Path):
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise sqlite3.OperationalError("database is locked")
        return "ok"

    assert _with_busy_retry(flaky, attempts=5, base_delay=0.001) == "ok"
    assert calls["n"] == 3

    mem = LessonMemory(tmp_path / "lessons.db")
    row = mem.conn.execute("PRAGMA busy_timeout").fetchone()
    assert row is not None
    assert int(row[0]) >= 30000
    lesson = mem.ingest_lesson("p", "t", "hello tags", tags=["a"], evidence_ids=["e1"])
    assert lesson is not None
    mem.close()


def test_ssrf_blocks_protocol_smuggling():
    for url, needle in (
        ("gopher://evil/1", "gopher"),
        ("file:///etc/passwd", "file"),
        ("dict://localhost:2628/x", "dict"),
        ("ftp://example.com/x", "ftp"),
    ):
        ok, reason = assert_public_url(url, resolve=False)
        assert ok is False
        assert needle in reason.lower()


def test_safe_exec_edge_metachars(tmp_path: Path):
    cmds = [
        "python -c pass && calc",
        "python -c pass || calc",
        "python -c pass " + chr(96) + "id" + chr(96),
        "python -c 'print(1)'" + "\n" + "whoami",
        "python -c pass $(whoami)",
    ]
    for cmd in cmds:
        with pytest.raises(ValueError, match="[Mm]etacharacter"):
            run_command_safely(cmd, cwd=tmp_path)


def test_safe_exec_empty_and_unicode(tmp_path: Path):
    with pytest.raises(ValueError, match="Empty"):
        run_command_safely("   ", cwd=tmp_path)
    argv = split_command("echo café")
    assert "café" in argv or any("caf" in a for a in argv)


def test_install_hint_mentions_three_oses():
    for tool in ("rg", "fd", "tesseract"):
        h = install_hint(tool)
        assert "Windows" in h or "winget" in h
        assert "Mac" in h or "brew" in h
        assert "Linux" in h or "apt" in h
