"""Compact MCP payloads — token budget."""

from __future__ import annotations

import json
from pathlib import Path

from godkiller_mcp.compact_io import dumps_payload
from godkiller_mcp.honesty import build_honesty_status
from godkiller_mcp.modes import ModeProtocolStore
from godkiller_mcp.runtime_paths import package_root


def test_dumps_payload_minified_by_default(monkeypatch):
    monkeypatch.delenv("GODKILLER_JSON_PRETTY", raising=False)
    s = dumps_payload({"a": 1, "b": [2, 3]})
    assert "\n" not in s
    assert s == '{"a":1,"b":[2,3]}'


def test_activate_omits_full_protocol_by_default():
    root = package_root() / ".agents"
    m = ModeProtocolStore(root)
    a = m.activate("plan", "build dashboard UI")
    assert a["compact"] is True
    assert a.get("protocol_markdown_omitted") is True
    assert "protocol_markdown" not in a
    assert "protocol_preview" in a
    assert "Burn tokens" not in json.dumps(a)
    assert "maximal tool swarm" not in json.dumps(a)
    fat = m.activate("plan", "x", include_protocol=True)
    assert "protocol_markdown" in fat
    assert len(json.dumps(fat)) > len(json.dumps(a))


def test_honesty_compact_smaller_than_detail():
    c = json.dumps(build_honesty_status())
    d = json.dumps(build_honesty_status(detail=True))
    assert len(c) < len(d)
    assert len(c) < 1800
    assert "actions_n" in build_honesty_status()["facades"]
    assert "host_mcp_configs" not in build_honesty_status()
    assert "per_config" in build_honesty_status(detail=True)["host_mcp"]
