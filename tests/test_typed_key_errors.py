"""P0 review fixes: typed KeyError + empty-as-missing."""

from __future__ import annotations

import json

import pytest

from godkiller_mcp.dispatch import handle_tool
from godkiller_mcp.governance import key_error_payload, missing_arg_error


def test_missing_arg_rejects_blank_string():
    assert missing_arg_error({"kind": "bugfix", "goal": ""}, "kind", "goal") == {
        "error": "missing_arg",
        "fields": ["goal"],
    }
    assert missing_arg_error({"kind": "bugfix", "goal": "   "}, "kind", "goal") == {
        "error": "missing_arg",
        "fields": ["goal"],
    }


def test_key_error_payload_unknown_task():
    p = key_error_payload(KeyError("Unknown task handle: task_abc"))
    assert p["error"] == "unknown_task"
    assert p["task_id"] == "task_abc"
    assert "open_task" in p["hint"]


def test_key_error_payload_field_name():
    assert key_error_payload(KeyError("prompt")) == {
        "error": "missing_arg",
        "fields": ["prompt"],
    }


def test_key_error_payload_internal():
    p = key_error_payload(KeyError("weird Key Error!"))
    assert p["error"] == "internal_key_error"


@pytest.mark.asyncio
async def test_unknown_task_not_labeled_missing_arg(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    # Force store home to empty tmp so task cannot exist
    from godkiller_mcp import dispatch as d
    from godkiller_mcp.evidence_store import EvidenceStore
    from godkiller_mcp.runtime_paths import tasks_dir

    store = EvidenceStore(persist_dir=tasks_dir(tmp_path))
    object.__setattr__(d.store, "_obj", store)

    out = await handle_tool("request_claim_done", {"task_id": "task_does_not_exist"})
    payload = json.loads(out[0].text)
    assert payload["error"] == "unknown_task"
    assert payload["error"] != "missing_arg"
