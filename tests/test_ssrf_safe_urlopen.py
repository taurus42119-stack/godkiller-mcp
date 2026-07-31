"""Tests for safe_urlopen redirect revalidation + DNS pin (SSRF)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from godkiller_mcp.ssrf import (
    SafeHTTPError,
    _PinnedResponse,
    assert_public_url,
    resolve_public_ips,
    safe_urlopen,
)


def test_assert_blocks_localhost():
    ok, reason = assert_public_url("http://127.0.0.1/x", resolve=False)
    assert ok is False
    assert "SSRF" in reason


def test_resolve_blocks_loopback_literal():
    ok, reason, ips = resolve_public_ips("127.0.0.1", 80)
    assert ok is False
    assert not ips
    assert "SSRF" in reason


def test_safe_urlopen_blocks_redirect_to_loopback():
    def _pinned(url, **kwargs):
        if "example.com" in url:
            return _PinnedResponse(302, {"Location": "http://127.0.0.1/secret"}, b"")
        raise AssertionError(f"unexpected pinned fetch {url}")

    with patch("godkiller_mcp.ssrf._request_pinned", side_effect=_pinned):
        with patch(
            "godkiller_mcp.ssrf.resolve_public_ips",
            side_effect=lambda host, port: (
                (False, "SSRF DENY: blocked IP 127.0.0.1", [])
                if host.startswith("127.")
                else (True, "ok", ["93.184.216.34"])
            ),
        ):
            with pytest.raises(SafeHTTPError) as ei:
                safe_urlopen("https://example.com/start", timeout=1)
    assert "127.0.0.1" in ei.value.reason or "SSRF" in ei.value.reason


def test_safe_urlopen_returns_body_on_200():
    with patch(
        "godkiller_mcp.ssrf._request_pinned",
        return_value=_PinnedResponse(200, {}, b'{"ok":true}'),
    ):
        with patch(
            "godkiller_mcp.ssrf.resolve_public_ips",
            return_value=(True, "ok", ["93.184.216.34"]),
        ):
            resp = safe_urlopen("https://example.com/api", timeout=1)
    assert resp.read() == b'{"ok":true}'


def test_safe_urlopen_pins_resolved_ip_not_hostname():
    seen = {}

    def _pinned(url, **kwargs):
        seen["ips"] = list(kwargs.get("pinned_ips") or [])
        return _PinnedResponse(200, {}, b"ok")

    with patch("godkiller_mcp.ssrf._request_pinned", side_effect=_pinned):
        with patch(
            "godkiller_mcp.ssrf.resolve_public_ips",
            return_value=(True, "ok", ["203.0.113.10"]),
        ):
            safe_urlopen("https://example.com/x", timeout=1)
    assert seen["ips"] == ["203.0.113.10"]


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
