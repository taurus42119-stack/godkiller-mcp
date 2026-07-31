"""Tests for safe_urlopen redirect revalidation (SSRF TOCTOU)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from godkiller_mcp.ssrf import SafeHTTPError, assert_public_url, safe_urlopen


def test_assert_blocks_localhost():
    ok, reason = assert_public_url("http://127.0.0.1/x", resolve=False)
    assert ok is False
    assert "SSRF" in reason


def test_safe_urlopen_blocks_redirect_to_loopback():
    class _Resp302:
        status = 302
        headers = {"Location": "http://127.0.0.1/secret"}

        def getcode(self):
            return 302

        def close(self):
            pass

        def read(self):
            return b""

    opener = MagicMock()
    opener.open.return_value = _Resp302()

    with patch("godkiller_mcp.ssrf._opener_no_redirect", return_value=opener):
        with patch(
            "godkiller_mcp.ssrf.assert_public_url",
            side_effect=lambda url, resolve=True: (
                (True, "ok")
                if "127.0.0.1" not in url
                else (False, "SSRF DENY: blocked IP 127.0.0.1")
            ),
        ):
            with pytest.raises(SafeHTTPError) as ei:
                safe_urlopen("https://example.com/start", timeout=1)
    assert "127.0.0.1" in ei.value.reason or "SSRF" in ei.value.reason


def test_safe_urlopen_returns_body_on_200():
    class _Resp200(io.BytesIO):
        status = 200
        headers = {}

        def getcode(self):
            return 200

        def close(self):
            pass

    body = _Resp200(b'{"ok":true}')
    opener = MagicMock()
    opener.open.return_value = body

    with patch("godkiller_mcp.ssrf._opener_no_redirect", return_value=opener):
        with patch("godkiller_mcp.ssrf.assert_public_url", return_value=(True, "ok")):
            resp = safe_urlopen("https://example.com/api", timeout=1)
    assert resp.read() == b'{"ok":true}'


def test_detect_hacking_path_escape():
    from godkiller_mcp.verify_bundle import detect_hacking

    blocked, reason = detect_hacking(
        "python -m pytest /etc/passwd",
        cwd=".",
    )
    assert blocked is True
    assert "escape" in reason.lower() or "workspace" in reason.lower()


def test_soak_blocks_disallowed_command(tmp_path):
    from godkiller_mcp.quality_gates import run_soak

    r = run_soak(
        command="curl http://evil.test",
        workspace=str(tmp_path),
    )
    assert r.passed is False
    assert "allowlist" in r.notes.lower() or "blocked" in r.notes.lower()
