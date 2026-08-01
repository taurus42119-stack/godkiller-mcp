"""Fault probe backup / unclean marker + theatre tags."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.fault_probe import probe_unclean, restore_probe_backups, run_fault_probe
from godkiller_mcp.quality_gates import build_compare_delta, build_competitor_scan
from godkiller_mcp.ship_mode import profile_label


def test_profile_label_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    assert profile_label() == "default"


def test_competitor_scan_not_claim_armor():
    r = build_competitor_scan(
        ["q"],
        [
            {"name": "A", "url": "https://example.com/a"},
            {"name": "B", "url": "https://example.com/b"},
        ],
    )
    p = r.to_payload()
    assert p["ceremony_complete"] is True
    assert p["passed"] is True
    assert p["claim_armor"] is False
    assert p["agent_supplied"] is True
    assert p["attested"] is False


def test_compare_delta_not_claim_armor():
    r = build_compare_delta({"ux": 1.0}, still_losing=False, best_competitor="Fake")
    p = r.to_payload()
    assert p["passed"] is True
    assert p["claim_armor"] is False
    assert p["agent_supplied"] is True


def test_quality_claim_ignores_agent_supplied_competitor_win():
    from godkiller_mcp.quality_gates import quality_claim_gates
    from godkiller_mcp.schema import Evidence, EvidenceType, Phase, TaskHandle, TaskKind, TaskState

    handle = TaskHandle(
        task_id="task_x",
        kind=TaskKind.FEATURE,
        goal="ui",
        phase=Phase.VERIFY,
        rubric_id="feature_v1",
        metadata={"ambition_ladder": "L1_presence", "require_visual": False},
    )
    state = TaskState(handle=handle)
    state.evidences.append(
        Evidence(
            task_id="task_x",
            type=EvidenceType.OTHER,
            summary="scan",
            payload={
                "source": "competitor_scan",
                "passed": True,
                "claim_armor": False,
                "agent_supplied": True,
            },
        )
    )
    state.evidences.append(
        Evidence(
            task_id="task_x",
            type=EvidenceType.OTHER,
            summary="delta",
            payload={
                "source": "compare_delta",
                "passed": True,
                "still_losing": False,
                "claim_armor": False,
                "agent_supplied": True,
            },
        )
    )
    ok, reason = quality_claim_gates(
        state, require_for_feature=True, require_competitor_loop=True
    )
    assert ok is True, reason


def test_fault_probe_leaves_original_and_clears_unclean(tmp_path: Path):
    mod = tmp_path / "calc.py"
    original = "def add(a, b):\n    return a + b\n"
    mod.write_text(original, encoding="utf-8")
    test = tmp_path / "test_calc.py"
    test.write_text(
        "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    report = run_fault_probe(
        workspace=tmp_path,
        target_file=mod,
        test_command="python -m pytest -q --tb=no",
        timeout_sec=30,
    )
    assert report.mutants_tried >= 1
    assert mod.read_text(encoding="utf-8") == original
    assert not probe_unclean(tmp_path)


def test_restore_probe_backups_from_unclean(tmp_path: Path):
    from godkiller_mcp.evidence_store import atomic_write_text

    mod = tmp_path / "calc.py"
    mod.write_text("GOOD\n", encoding="utf-8")
    backup = tmp_path / ".godkiller" / "probe_backup"
    backup.mkdir(parents=True)
    (backup / "calc.py.bak").write_text("GOOD\n", encoding="utf-8")
    # Simulate crash: mutant left on disk + unclean marker
    mod.write_text("MUTANT\n", encoding="utf-8")
    unclean = tmp_path / ".godkiller" / "probe_unclean.json"
    atomic_write_text(
        unclean,
        '{"files": ["calc.py"], "bak": "x"}',
    )
    assert probe_unclean(tmp_path)
    info = restore_probe_backups(tmp_path)
    assert "calc.py" in info["restored"]
    assert mod.read_text(encoding="utf-8") == "GOOD\n"
    assert not probe_unclean(tmp_path)


def test_host_finalize_labels_theatre_risk():
    from godkiller_mcp.council_agents import CouncilDebateEngine

    eng = CouncilDebateEngine()
    start = eng.start_host("def f():\n    return 1\n", {})
    sid = start["session_id"]
    for role in ("coder", "hacker", "optimizer"):
        vote = "REJECT" if role == "hacker" else "APPROVE"
        critique = (
            "Missing bounds check on user input path and no regression test coverage."
            if role == "hacker"
            else "looks fine"
        )
        must = ["add bounds check", "add unit test"] if role == "hacker" else []
        eng.submit_opinion(sid, role, vote, critique=critique, severity=8, must_fix=must)
    # Round 2 approve after reject
    fin1 = eng.finalize_host(sid, advance_round=True)
    assert fin1.get("verdict") == "COUNCIL_IN_PROGRESS"
    for role in ("coder", "hacker", "optimizer"):
        eng.submit_opinion(
            sid,
            role,
            "APPROVE",
            critique="Addressed bounds and tests after prior reject.",
            severity=2,
            must_fix=[],
        )
    fin = eng.finalize_host(sid)
    assert fin.get("mode") == "host"
    assert fin.get("theatre_risk") is True
    assert fin.get("verdict") == "COUNCIL_PASS"


def test_ship_rejects_host_theatre_council(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_HOST_COUNCIL", raising=False)
    from godkiller_mcp.claim_armor import claim_council_gate
    from godkiller_mcp.evidence_store import EvidenceStore
    from godkiller_mcp.schema import EvidenceType, TaskKind

    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council host theatre",
        {
            "source": "council_finalize",
            "server_authored": True,
            "mode": "host",
            "theatre_risk": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {"vote": "APPROVE", "critique": "ok after fix", "must_fix": []},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "transcript": [
                {
                    "round": 1,
                    "opinions": {
                        "hacker": {
                            "vote": "REJECT",
                            "critique": "Missing auth on write path and no tests for escape.",
                            "must_fix": ["add auth", "add test"],
                            "severity": 8,
                        }
                    },
                }
            ],
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "theatre_risk" in reason.lower()


def test_dev_host_theatre_warns_but_may_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    from godkiller_mcp.claim_armor import claim_council_gate
    from godkiller_mcp.evidence_store import EvidenceStore
    from godkiller_mcp.schema import EvidenceType, TaskKind

    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council host theatre",
        {
            "source": "council_finalize",
            "server_authored": True,
            "mode": "host",
            "theatre_risk": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {"vote": "APPROVE", "critique": "ok after fix", "must_fix": []},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "transcript": [
                {
                    "round": 1,
                    "opinions": {
                        "hacker": {
                            "vote": "REJECT",
                            "critique": "Missing auth on write path and no tests for escape.",
                            "must_fix": ["add auth", "add test"],
                            "severity": 8,
                        }
                    },
                }
            ],
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is True, reason
    assert reason.startswith("WARNING:")
    assert "theatre_risk" in reason.lower()


def test_confidence_ignores_client_search_hits(tmp_path: Path):
    from godkiller_mcp.code_intel import EpistemicConfidenceGate

    f = tmp_path / "mod.py"
    f.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    eng = EpistemicConfidenceGate()
    inflated = eng.evaluate(
        str(f),
        known_symbols=["alpha"],
        has_searched=True,
        search_hit_count=99,
    )
    assert inflated["metrics"]["client_search_ignored"] is True
    assert inflated["metrics"]["search_hit_count"] is None
    # Must not reach ~90 from fake hits alone
    assert inflated["readiness_score"] < 90
    assert inflated["score"] == inflated["readiness_score"]
