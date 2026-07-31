"""P2 repair_wake — brain loop after failure; self_heal unchanged."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.repair_wake import (
    clear_after_verify_pass,
    mark_repair_required,
    merge_wake_into,
    record_repair_wake,
    require_repair_clear,
)
from godkiller_mcp.schema import TaskKind


def test_repair_blocks_edit_when_armed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    meta = {"repair_wake": mark_repair_required({}, reason="tests red", source="verify_bundle")}
    ok, reason = require_repair_clear(meta)
    assert ok is False
    assert "repair_wake" in reason.lower() or "repair wake" in reason.lower()


def test_repair_wake_rejects_hollow_diagnosis():
    bad = record_repair_wake(diagnosis="asdfasdfasdf", hypotheses=["a", "b", "c"])
    assert bad["ok"] is False


def test_repair_wake_ok_then_verify_clears(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    armed = mark_repair_required({}, reason="verify failed on login test", source="verify_bundle")
    wake = record_repair_wake(
        diagnosis=(
            "Login test fails because session cookie is not set after POST /login "
            "when CSRF token is missing from the form."
        ),
        hypotheses=[
            "CSRF middleware rejects POST before session write",
            "Test client does not follow redirect that sets cookie",
            "Fixture uses wrong secret key so cookie signature fails",
        ],
        self_heal_used=True,
    )
    assert wake["ok"] is True, wake
    merged = merge_wake_into(armed, wake)
    assert merged["required"] is False
    assert merged["verify_pending"] is True
    ok, _ = require_repair_clear({"repair_wake": merged})
    assert ok is True
    cleared = clear_after_verify_pass({"repair_wake": merged})
    assert cleared["verify_pending"] is False
    assert cleared["streak"] == 0


def test_touches_plan_needs_refute():
    wake = record_repair_wake(
        diagnosis=(
            "Chosen design step is wrong: we assumed sync API but product needs async workers."
        ),
        hypotheses=[
            "Queue backlog explains timeout under load",
            "Worker concurrency too low for peak traffic",
            "Missing retry policy causes silent drop",
        ],
        touches_plan=True,
        plan_refute_ok=False,
    )
    assert wake["ok"] is False
    assert "plan" in wake["reason"].lower()


def test_escalate_streak():
    meta: dict = {}
    for i in range(3):
        meta["repair_wake"] = mark_repair_required(
            meta, reason=f"fail {i}", source="verify_bundle"
        )
    assert meta["repair_wake"]["escalated"] is True
    assert meta["repair_wake"]["streak"] == 3


def test_facade_repair_wake():
    from godkiller_mcp.server import FACADE_ACTIONS

    assert FACADE_ACTIONS["gk_mode"]["repair_wake"] == "ultradeep_repair_wake"


def test_self_heal_still_importable():
    from godkiller_mcp.code_intel import SelfHealingEngine

    eng = SelfHealingEngine()
    out = eng.heal("godkiller_repo_map", "FileNotFoundError: no such file", {"root_dir": "."})
    assert "recommended_tool" in out or "diagnosis" in out
