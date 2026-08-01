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
    # Full maps only when detail=true
    fat = build_honesty_status(detail=True)
    assert fat.get("compact") is False
    assert "status" in fat["this_server_facades"]["actions"]["gk_meta"]
    assert fat["runtime"]["not_enterprise"] is True
    assert fat["agents_constitution"]["must_read_agents_md"] is True


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
    assert len(out[0].text) < 2500  # keep status cheap
