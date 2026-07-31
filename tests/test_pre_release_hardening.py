"""Pre-release hardening: safe_exec no shell, SSRF weird IPs."""

from __future__ import annotations

import pytest

from godkiller_mcp.safe_exec import run_command_safely
from godkiller_mcp.ssrf import assert_public_url


def test_safe_exec_never_shell_true(tmp_path, monkeypatch):
    # Missing executable must fail closed — no shell=True path
    with pytest.raises(FileNotFoundError, match="refuses shell=True"):
        run_command_safely("this_binary_does_not_exist_zz 1", cwd=tmp_path, timeout_sec=5)


def test_safe_exec_rejects_metachar(tmp_path):
    with pytest.raises(ValueError, match="metacharacter"):
        run_command_safely("python -c pass & calc", cwd=tmp_path)


def test_ssrf_blocks_octal_loopback():
    ok, reason = assert_public_url("http://0177.0.0.1/")
    assert ok is False
    assert "octal" in reason.lower() or "SSRF" in reason


def test_ssrf_blocks_hex_int_loopback():
    ok, reason = assert_public_url("http://0x7f000001/")
    assert ok is False


def test_ssrf_blocks_decimal_loopback():
    # 127.0.0.1 as integer
    ok, reason = assert_public_url("http://2130706433/")
    assert ok is False
