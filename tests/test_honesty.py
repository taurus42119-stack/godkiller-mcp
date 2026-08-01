"""Honesty status + mouth rules (disk truth over chat narration)."""

from __future__ import annotations

import asyncio

from godkiller_mcp.agents_constitution import constitution_status, resolve_agents_md
from godkiller_mcp.honesty import build_honesty_status, honesty_rules
from godkiller_mcp.server import FACADE_ACTIONS


def test_honesty_rules_cover_core_mouth():
    rules = " ".join(honesty_rules(detail=True)).lower()
    assert "invent" in rules
    assert "enterprise" in rules
    assert "claim" in rules
    assert "agents_md" in rules or "constitution" in rules or "visual_step" in rules
    st = build_honesty_status()
    assert "disk" in st["mouth"].lower() or "invent" in st["mouth"].lower()


def test_constitution_resolves():
    md = resolve_agents_md()
    assert md is not None
    assert md.is_file()
    st = constitution_status()
    assert st["must_read_agents_md"] is True
    assert st["exists"] is True
    assert st["agents_md_path"]
    assert st["has_visual_qa_rule_8"] is True


def test_build_honesty_status_shape():
    st = build_honesty_status()
    assert st["ok"] is True
    assert st.get("compact") is True
    assert st["runtime"]["profile"]
    assert "seal" in st["runtime"]
    assert "gk_meta" in st["facades"]["facades"]
    assert "actions_n" in st["facades"]
    assert "host_mcp_configs" not in st  # ultra-compact: no 5x duplicate dumps
    assert "servers" in st["host_mcp"]
    assert st["agents_ok"] is True
    assert st["agents_md"]
    assert "write_guard" in st
    assert st["write_guard"]["severity"] in ("ok", "warn")
    assert st["write_guard"].get("msg")
    fat = build_honesty_status(detail=True)
    assert fat.get("compact") is False
    assert "status" in fat["this_server_facades"]["actions"]["gk_meta"]
    assert fat["runtime"]["not_enterprise"] is True
    assert fat["agents_constitution"]["must_read_agents_md"] is True
    assert "write_guard" in fat


def test_write_guard_status_warn_without_heartbeat(monkeypatch, tmp_path):
    from pathlib import Path

    from godkiller_mcp import write_guard as wg

    monkeypatch.delenv("GODKILLER_WRITE_GUARD_WIRED", raising=False)
    monkeypatch.setattr(wg, "_host_marker_path", lambda: tmp_path / "missing.json")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.chdir(tmp_path)
    st = wg.write_guard_host_status()
    assert st["severity"] == "warn"
    assert st["wired_hint"] is False

    marker = tmp_path / "write_guard_host.json"
    marker.write_text('{"wired_hint": true}', encoding="utf-8")
    monkeypatch.setattr(wg, "_host_marker_path", lambda: marker)
    st2 = wg.write_guard_host_status()
    assert st2["severity"] == "ok"
    assert st2["wired_hint"] is True


def test_facade_maps_honesty_status():
    assert FACADE_ACTIONS["gk_meta"]["status"] == "gk_honesty_status"


def test_dispatch_honesty_status():
    from godkiller_mcp.dispatch import handle_tool

    out = asyncio.run(handle_tool("gk_honesty_status", {}))
    assert out and hasattr(out[0], "text")
    import json

    data = json.loads(out[0].text)
    assert data.get("ok") is True
    assert data.get("compact") is True
    assert data.get("agents_ok") is True
    assert "host_mcp" in data
    assert "write_guard" in data
    assert len(out[0].text) < 3200  # keep status cheap (incl. write_guard warn)
