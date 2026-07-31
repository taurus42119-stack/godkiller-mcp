"""tool_propose — search≠install gate (additive, harsh)."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import TaskKind
from godkiller_mcp.tool_propose import (
    approve,
    claim_tool_propose_gate,
    propose,
    record_used,
    reject_all,
)


def _five(prefix: str = "https://pypi.org/project") -> list[dict]:
    names = ["requests", "httpx", "urllib3", "aiohttp", "certifi"]
    out = []
    for i, n in enumerate(names):
        out.append(
            {
                "id": f"c{i+1}",
                "name": n,
                "url": f"{prefix}/{n}/",
                "reason": f"Need {n} for reliable HTTP client capabilities in this workspace task.",
                "risk": "third-party package supply chain",
                "kind": "pypi",
            }
        )
    return out


def test_propose_rejects_too_few():
    out = propose("Need better HTTP tooling for API work", _five()[:3])
    assert out["ok"] is False
    assert "≥5" in out["reason"] or "5" in out["reason"]


def test_propose_rejects_localhost():
    cands = _five()
    cands[0]["url"] = "http://localhost:8080/tool"
    out = propose("Need better HTTP tooling for API work", cands)
    assert out["ok"] is False


def test_propose_rejects_hollow_reason():
    cands = _five()
    cands[0]["reason"] = "ok fine todo"
    out = propose("Need better HTTP tooling for API work", cands)
    assert out["ok"] is False
    assert "hollow" in out["reason"]


def test_approve_used_gate_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    out = propose("Need better HTTP tooling for API work", _five(), workspace=str(tmp_path))
    assert out["ok"] is True
    st = out["tool_propose"]
    ap = approve(st, ["c1", "c2"], workspace=str(tmp_path))
    assert ap["ok"] is True
    assert Path(ap["hint_path"]).is_file()
    assert "HINT ONLY" in Path(ap["hint_path"]).read_text(encoding="utf-8")

    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "ship http")
    store.update_metadata(state.handle.task_id, {"tool_propose": ap["tool_propose"], "mode": "ultradeep"})
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "tool_used" in reason

    u1 = record_used(ap["tool_propose"], "c1", "Called requests.get against public API and parsed JSON.")
    assert u1["ok"] is True
    u2 = record_used(u1["tool_propose"], "c2", "Used httpx.AsyncClient for concurrent fetch in script.")
    assert u2["ok"] is True
    store.update_metadata(state.handle.task_id, {"tool_propose": u2["tool_propose"]})
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_reject_all_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    out = propose("Need better HTTP tooling for API work", _five(), workspace=str(tmp_path))
    st = out["tool_propose"]
    bad = reject_all(st, "too short")
    assert bad["ok"] is False

    good = reject_all(
        st,
        "Existing stdlib urllib and current MCP scrape tools already cover HTTP fetch needs "
        "for this task without adding packages.",
    )
    assert good["ok"] is True
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix")
    store.update_metadata(
        state.handle.task_id,
        {"tool_propose": good["tool_propose"], "mode": "debug"},
    )
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_pending_approve_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    out = propose("Need better HTTP tooling for API work", _five(), workspace=str(tmp_path))
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "x")
    store.update_metadata(state.handle.task_id, {"tool_propose": out["tool_propose"], "mode": "plan"})
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "approve" in reason.lower() or "reject" in reason.lower()


def test_ask_mode_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "q")
    store.update_metadata(state.handle.task_id, {"mode": "ask"})
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is True
    assert "ask" in reason.lower()


def test_ship_ignores_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.setenv("GODKILLER_TOOL_PROPOSE", "0")
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "x")
    store.update_metadata(state.handle.task_id, {"mode": "ultradeep"})
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "tool_propose" in reason.lower() or "5" in reason


def test_relax_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DEV_RELAX", "1")
    monkeypatch.setenv("GODKILLER_TOOL_PROPOSE", "0")
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.FEATURE, "x")
    ok, reason = claim_tool_propose_gate(store.get(state.handle.task_id))
    assert ok is True
    assert "skip" in reason.lower()


def test_facade_actions():
    from godkiller_mcp.server import FACADE_ACTIONS

    m = FACADE_ACTIONS["gk_mode"]
    assert m["tool_propose"] == "tool_propose"
    assert m["tool_approve"] == "tool_approve"
    assert m["tool_reject"] == "tool_reject_all"
    assert m["tool_used"] == "tool_used"
