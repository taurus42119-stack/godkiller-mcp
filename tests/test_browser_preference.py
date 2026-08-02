"""chrome-devtools preferred over gk_browser when listed on host."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.browser_preference import (
    browser_preference_status,
    chrome_devtools_listed,
    gk_browser_gate,
)


def test_chrome_devtools_detected_from_name():
    ok, name = chrome_devtools_listed(["chrome-devtools", "godkiller"])
    assert ok is True
    assert name == "chrome-devtools"


def test_gate_redirects_when_cdt_listed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"chrome-devtools": {"command": "npx"}, "godkiller": {}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "godkiller_mcp.honesty.mcp_config_candidates",
        lambda: [cfg],
    )
    monkeypatch.delenv("GODKILLER_PREFER_GK_BROWSER", raising=False)
    blocked = gk_browser_gate({})
    assert blocked is not None
    assert blocked["error"] == "prefer_chrome_devtools"
    assert blocked["preferred"] == "chrome-devtools"


def test_gate_allows_when_cdt_absent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(json.dumps({"mcpServers": {"godkiller": {}}}), encoding="utf-8")
    monkeypatch.setattr(
        "godkiller_mcp.honesty.mcp_config_candidates",
        lambda: [cfg],
    )
    monkeypatch.delenv("GODKILLER_PREFER_GK_BROWSER", raising=False)
    assert gk_browser_gate({}) is None


def test_force_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"chrome-devtools": {"command": "npx"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "godkiller_mcp.honesty.mcp_config_candidates",
        lambda: [cfg],
    )
    assert gk_browser_gate({"force_gk_browser": 1}) is None
    monkeypatch.setenv("GODKILLER_PREFER_GK_BROWSER", "1")
    assert gk_browser_gate({}) is None


def test_status_primary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    cfg = tmp_path / "mcp.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"chrome-devtools": {"command": "npx"}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "godkiller_mcp.honesty.mcp_config_candidates",
        lambda: [cfg],
    )
    monkeypatch.delenv("GODKILLER_PREFER_GK_BROWSER", raising=False)
    st = browser_preference_status()
    assert st["primary"] == "chrome-devtools"
    assert st["chrome_devtools_listed"] is True
