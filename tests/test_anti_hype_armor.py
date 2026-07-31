"""Anti-hype armor: exit preflight, council refute-first, quality no self-score."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.claim_armor import claim_council_gate, claim_exit_preflight_gate
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.hollow_surface import scan_hollow_surface
from godkiller_mcp.quality_gates import build_compare_delta, build_competitor_scan, run_soak
from godkiller_mcp.schema import EvidenceType, TaskKind


def test_hollow_catches_tsx_placeholder(tmp_path: Path):
    f = tmp_path / "App.tsx"
    f.write_text("export const X = () => <div>Coming soon</div>;\n", encoding="utf-8")
    report = scan_hollow_surface([tmp_path])
    assert report.clean is False
    assert any(x.kind == "web_placeholder" for x in report.findings)


def test_exit_preflight_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    ok, reason = claim_exit_preflight_gate(state)
    assert ok is False
    assert "exit_checklist" in reason.lower() or "gk_verify.exit" in reason.lower()


def test_exit_preflight_accepts_pass_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "exit ok",
        {
            "source": "exit_checklist",
            "directive": "pass",
            "status": "ready",
            "blocking": [],
            "server_authored": True,
        },
        server_authored=True,
    )
    ok, reason = claim_exit_preflight_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_council_refute_first_blocks_rubber_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    # Three APPROVE with empty hacker critique — hype
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council fake",
        {
            "source": "council_finalize",
            "server_authored": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {"vote": "APPROVE", "critique": "ok", "must_fix": [], "severity": 1},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": [], "severity": 1},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": [], "severity": 1},
            "final_opinions": {
                "hacker": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            },
            "transcript": [],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "refute" in reason.lower()


def test_council_pass_with_hacker_refute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council ok",
        {
            "source": "council_finalize",
            "server_authored": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {
                "vote": "APPROVE",
                "critique": "Fixed after reject.",
                "must_fix": [],
                "severity": 2,
            },
            "coder": {"vote": "APPROVE", "critique": "looks correct now", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "fine", "must_fix": []},
            "transcript": [
                {
                    "round": 1,
                    "opinions": {
                        "hacker": {
                            "vote": "REJECT",
                            "critique": "eval() on user input is dangerous and must be removed before claim.",
                            "must_fix": ["remove eval call on untrusted input"],
                            "severity": 9,
                        },
                        "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                        "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                    },
                }
            ],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_council_empty_reject_then_approve_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council theatre",
        {
            "source": "council_finalize",
            "server_authored": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {"vote": "APPROVE", "critique": "ok now", "must_fix": [], "severity": 1},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "transcript": [
                {
                    "round": 1,
                    "opinions": {
                        "hacker": {
                            "vote": "REJECT",
                            "critique": "ok",
                            "must_fix": [],
                            "severity": 9,
                        },
                        "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                        "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
                    },
                }
            ],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "substantial" in reason.lower() or "refute" in reason.lower()


def test_council_long_critique_alone_is_not_refute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council soft",
        {
            "source": "council_finalize",
            "server_authored": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {
                "vote": "APPROVE",
                "critique": "x" * 80,
                "must_fix": [],
                "severity": 1,
            },
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "transcript": [],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "refute" in reason.lower()


def test_soak_self_score_fails_without_command(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    r = run_soak(errors=0, stuck_pct=0, command=None, workspace=None)
    assert r.passed is False


def test_competitor_needs_http_urls():
    r = build_competitor_scan(
        ["accounting saas"],
        [{"name": "FakeCo", "url": ""}, {"name": "Other", "url": "not-a-url"}],
    )
    assert r.passed is False
    r2 = build_competitor_scan(
        ["accounting saas"],
        [
            {"name": "A", "url": "https://a.example"},
            {"name": "B", "url": "https://b.example"},
        ],
    )
    assert r2.passed is True


def test_compare_cannot_self_score_win_with_empty_axes():
    r = build_compare_delta({}, still_losing=False, best_competitor="")
    assert r.passed is False
    r2 = build_compare_delta(
        {"ux": 1.0, "speed": 0.5},
        still_losing=False,
        best_competitor="RivalCo",
    )
    assert r2.passed is True
