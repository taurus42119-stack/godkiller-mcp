"""Claim verdict: blocked is machine status, not chat tone."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.claim_verdict import build_claim_payload, classify_from_reason
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.policy import PolicyEngine
from godkiller_mcp.schema import TaskKind


def test_classify_layers():
    assert classify_from_reason("stale evidence: material_hash no longer matches") == "freshness"
    assert classify_from_reason("fault_probe SURVIVORS=2") == "fault_probe"
    assert classify_from_reason("verify_bundle evidence missing") == "verify"


def test_blocked_payload_contract():
    p = build_claim_payload(
        allowed=False,
        reason="verify_bundle evidence missing",
        gate="verify",
        action="block",
        detail=True,
    )
    assert p["status"] == "blocked"
    assert p["verdict"] == "NOT_DONE"
    assert p["gate"] == "verify"
    assert p["agent_role"]["may_decide_done"] is False
    assert p["agent_role"]["chat_summary_is_not_status"] is True
    assert "verify" in p["next"].lower() or "bundle" in p["next"].lower()


def test_blocked_payload_compact_omits_mouth():
    p = build_claim_payload(
        allowed=False,
        reason="verify_bundle evidence missing",
        gate="verify",
        action="block",
    )
    assert p["status"] == "blocked"
    assert "agent_role" not in p
    assert "honest_mouth" not in p
    assert p["next"]


def test_done_payload_contract():
    p = build_claim_payload(allowed=True, reason="ok", gate="ok", action="allow_claim_done")
    assert p["status"] == "done"
    assert p["verdict"] == "DONE"
    assert p["gate"] == "ok"


def test_policy_claim_returns_gate_and_blocked_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix nothing")
    allowed, results, reason, gate = PolicyEngine().request_claim_done(
        state,
        require_blast_radius=False,
        require_quality_loop=False,
        require_competitor_loop=False,
    )
    assert allowed is False
    assert gate
    payload = build_claim_payload(
        allowed=allowed,
        reason=reason,
        gate=gate,
        results=results,
        action="block",
        detail=True,
    )
    assert payload["status"] == "blocked"
    assert payload["verdict"] == "NOT_DONE"
    assert payload["agent_role"]["may_propose_done"] is True
    assert payload["agent_role"]["may_decide_done"] is False
