"""Tests for safe_urlopen redirect revalidation + DNS pin (SSRF)."""

from __future__ import annotations

import json
import urllib.request
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


def test_detect_hacking_ruff_mypy_path_escape(tmp_path):
    from godkiller_mcp.verify_bundle import detect_hacking

    blocked, reason = detect_hacking("ruff check /etc/passwd", cwd=tmp_path)
    assert blocked is True
    assert "escape" in reason.lower() or "workspace" in reason.lower()

    blocked2, reason2 = detect_hacking("mypy ../../secrets", cwd=tmp_path)
    assert blocked2 is True
    assert "escape" in reason2.lower() or "workspace" in reason2.lower()

    ok, _ = detect_hacking("ruff check .", cwd=tmp_path)
    assert ok is False


def test_fault_probe_blocks_pytest_outside_workspace(tmp_path):
    from godkiller_mcp.fault_probe import run_fault_probe

    mod = tmp_path / "calc.py"
    mod.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    report = run_fault_probe(
        workspace=tmp_path,
        target_file=mod,
        test_command="python -m pytest /etc/passwd -q",
        timeout_sec=10,
        max_mutants=1,
    )
    assert report.clean is False
    assert report.skipped_reason
    assert "blocked" in (report.skipped_reason or "").lower() or "escape" in (
        report.skipped_reason or ""
    ).lower() or "workspace" in (report.skipped_reason or "").lower()


def test_soak_blocks_disallowed_command(tmp_path):
    from godkiller_mcp.quality_gates import run_soak

    r = run_soak(
        command="curl http://evil.test",
        workspace=str(tmp_path),
    )
    assert r.passed is False
    assert "allowlist" in r.notes.lower() or "blocked" in r.notes.lower()


def test_llm_client_uses_safe_urlopen(monkeypatch):
    """chat_completion must not call raw urllib.request.urlopen."""
    import godkiller_mcp.llm_client as lc

    calls = {"safe": 0, "raw": 0}

    class _Resp:
        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": '{"vote":"PASS"}'}}]}
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _safe(*a, **k):
        calls["safe"] += 1
        return _Resp()

    def _raw(*a, **k):
        calls["raw"] += 1
        raise AssertionError("raw urlopen must not be used")

    monkeypatch.setattr(lc, "safe_urlopen", _safe)
    monkeypatch.setattr(urllib.request, "urlopen", _raw)
    cfg = lc.LLMConfig(api_key="sk-test", base_url="https://api.openai.com/v1")
    out = lc.chat_completion(cfg, "sys", "user")
    assert "PASS" in out or "vote" in out
    assert calls["safe"] == 1
    assert calls["raw"] == 0