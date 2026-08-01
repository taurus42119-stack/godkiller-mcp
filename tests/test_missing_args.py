"""Slice B: missing required args return JSON, not raw KeyError."""

from __future__ import annotations

import json

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.governance import missing_arg_error


def test_missing_arg_error_helper():
    assert missing_arg_error({"kind": "bugfix"}, "kind", "goal") == {
        "error": "missing_arg",
        "fields": ["goal"],
    }
    assert missing_arg_error({"kind": "bugfix", "goal": "x"}, "kind", "goal") is None
    assert missing_arg_error(None, "kind") == {"error": "missing_arg", "fields": ["kind"]}


@pytest.mark.asyncio
async def test_open_task_missing_goal_json():
    out = await handle_tool("open_task", {"kind": "bugfix"})
    payload = json.loads(out[0].text)
    assert payload["error"] == "missing_arg"
    assert "goal" in payload["fields"]


@pytest.mark.asyncio
async def test_keyerror_net_on_unregistered_path():
    """Tools still on dispatch body get KeyError → missing_arg JSON."""
    out = await handle_tool("godkiller_route_intent", {})
    payload = json.loads(out[0].text)
    assert payload["error"] == "missing_arg"
    assert "prompt" in payload["fields"]
