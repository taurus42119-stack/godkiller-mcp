"""Phase 0 critic-kill + Phase 1 view/ultradeep plan_refute."""

from __future__ import annotations

import ipaddress
from pathlib import Path
from unittest.mock import patch

import pytest

from godkiller_mcp.claim_armor import claim_council_gate
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.ssrf import assert_public_url
from godkiller_mcp.ultradeep_engine import record_plan_refute, require_plan_refute_hold
from godkiller_mcp.verify_bundle import detect_hacking
from godkiller_mcp import view_engine as ve


def test_pytest_deny_override_ini():
    blocked, reason = detect_hacking("python -m pytest -q --override-ini=cache_dir=/tmp")
    assert blocked
    assert "deny-list" in reason.lower() or "override" in reason.lower()


def test_pytest_deny_dash_c():
    blocked, reason = detect_hacking("pytest -c /etc/evil.ini")
    assert blocked


def test_pytest_deny_pyargs():
    blocked, _ = detect_hacking("python -m pytest --pyargs evilpkg")
    assert blocked


def test_pytest_allow_normal():
    blocked, reason = detect_hacking("python -m pytest -q tests/")
    assert not blocked, reason


def test_ssrf_blocks_loopback_literal():
    ok, reason = assert_public_url("http://127.0.0.1/secret")
    assert ok is False
    assert "SSRF" in reason


def test_ssrf_blocks_metadata_host():
    ok, reason = assert_public_url("http://169.254.169.254/latest/meta-data/")
    assert ok is False


def test_ssrf_blocks_private_resolved(monkeypatch: pytest.MonkeyPatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(0, 0, 0, "", ("10.0.0.5", port))]

    monkeypatch.setattr("godkiller_mcp.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    ok, reason = assert_public_url("https://evil.internal.example/x")
    assert ok is False
    assert "10.0.0.5" in reason or "blocked" in reason.lower()


def test_ssrf_allows_public_resolved(monkeypatch: pytest.MonkeyPatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(0, 0, 0, "", ("93.184.216.34", port))]  # example.com-ish public

    monkeypatch.setattr("godkiller_mcp.ssrf.socket.getaddrinfo", fake_getaddrinfo)
    ok, reason = assert_public_url("https://example.com/")
    assert ok is True, reason


def test_council_nits_must_fix_not_enough(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "council nits",
        {
            "source": "council_finalize",
            "server_authored": True,
            "verdict": "COUNCIL_PASS",
            "consensus_reached": True,
            "hacker": {"vote": "APPROVE", "critique": "nits only", "must_fix": ["nits"], "severity": 1},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "final_opinions": {
                "hacker": {"vote": "APPROVE", "must_fix": ["nits"]},
                "coder": {"vote": "APPROVE", "must_fix": []},
                "optimizer": {"vote": "APPROVE", "must_fix": []},
            },
            "transcript": [],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "REJECT" in reason


def test_council_reject_in_transcript_still_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
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
            "hacker": {"vote": "APPROVE", "critique": "fixed", "must_fix": [], "severity": 2},
            "coder": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "optimizer": {"vote": "APPROVE", "critique": "ok", "must_fix": []},
            "transcript": [
                {
                    "round": 1,
                    "opinions": {
                        "hacker": {
                            "vote": "REJECT",
                            "critique": "dangerous eval path on user input must be removed before claim.",
                            "must_fix": ["remove eval usage now"],
                            "severity": 9,
                        }
                    },
                }
            ],
            "static_security_block": False,
        },
        server_authored=True,
    )
    ok, reason = claim_council_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_plan_refute_requires_findings_and_searches():
    bad = record_plan_refute(findings=["short"], search_queries=["a"], decision="HOLD")
    assert bad["ok"] is False
    good_findings = [f"attack finding number {i} against plan step" for i in range(8)]
    good_q = [f"query about plan risk {i}" for i in range(5)]
    ok = record_plan_refute(findings=good_findings, search_queries=good_q, decision="HOLD")
    assert ok["ok"] is True
    assert ok["status"] == "HOLD"


def test_edit_blocked_without_plan_refute(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    meta = {"plan_validation": {"valid": True}}
    ok, reason = require_plan_refute_hold(meta)
    assert ok is False
    assert "plan_refute" in reason.lower() or "ultradeep_plan_refute" in reason.lower()


def test_view_pipeline_g1_minima(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "0")
    monkeypatch.setattr(
        "godkiller_mcp.ssrf.assert_public_url",
        lambda url, resolve=True: (True, "ok"),
    )
    out = ve.start_view("critique rival paper", gravity="G1", task_id="t1")
    state = out["view"]
    thr = ve.thresholds("G1")
    # fail attack before enough searches
    bad = ve.record_attack(
        state,
        {
            "text": "method is underspecified for the claim",
            "quote": "The authors provide no ablation for X feature choices.",
            "doi_or_url": "https://arxiv.org/abs/1234.5678",
            "locator": "p.4",
            "stance": "undermines",
            "taxonomy": "method",
            "severity": 8,
        },
    )
    assert bad["ok"] is False

    # diverse hosts (not example.com — blocked as placeholder)
    hosts = [
        "arxiv.org",
        "nature.com",
        "science.org",
        "acm.org",
        "ieee.org",
        "springer.com",
        "wiley.com",
        "plos.org",
        "nih.gov",
        "ox.ac.uk",
        "mit.edu",
        "stanford.edu",
    ]
    for i in range(thr["min_searches"]):
        r = ve.record_search(
            state,
            query=f"expert critique sampling bias topic {i}",
            url=f"https://{hosts[i % len(hosts)]}/paper/{i}",
        )
        assert r["ok"] is True, r
        state = r["view"]

    for i in range(thr["min_attacks"]):
        r = ve.record_attack(
            state,
            {
                "text": f"weakness slot {i} on sampling bias and statistical power analysis",
                "quote": f"Sample size justification is absent for cohort {i} primary analysis.",
                "doi_or_url": f"10.1234/journal.attack{i}",
                "locator": f"p.{i+1}",
                "stance": "contradicts",
                "taxonomy": "data",
                "severity": 7,
                "outcompete": "Run pre-registered power analysis",
            },
        )
        assert r["ok"] is True, r
        state = r["view"]

    steps = {
        k: f"Adversarial content for {k} — kill criteria and outcompete path with falsifiers. "
        + ("detail " * 8)
        for k in ve.NINE_STEPS
    }
    d = ve.draft_plan(state, steps)
    assert d["ok"] is True, d
    state = d["view"]

    findings = [
        {
            "text": (
                f"Plan step hole {i}: rollout lacks falsifier experiment detail "
                f"and ignores rival baseline {i} from literature"
            ),
            "step": "9_rollout_verify",
        }
        for i in range(thr["min_refute"])
    ]
    ref = ve.refute_plan(state, findings=findings, decision="HOLD")
    assert ref["ok"] is True, ref
    state = ref["view"]

    praise = ve.finalize(state, "Overall good paper with minor gaps. " + ("y" * 200))
    assert praise["ok"] is False

    fin = ve.finalize(
        state,
        (
            "Weaknesses: sampling bias, unreproducible preprocessing, overclaimed generalization. "
            "Gaps vs rivals remain on external validity. Fail modes include silent data leakage. "
            "Outcompete via pre-registration, larger held-out cohort, and adversarial eval suite."
        ),
    )
    assert fin["ok"] is True, fin


def test_plan_refute_rejects_asdf_spam():
    spam = [f"asdfasdfasdfasdf {i}" for i in range(10)]
    qs = [f"query about plan risk {i}" for i in range(5)]
    bad = record_plan_refute(findings=spam, search_queries=qs, decision="HOLD")
    assert bad["ok"] is False


def test_view_rejects_example_com_placeholder(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "0")
    monkeypatch.setattr(
        "godkiller_mcp.ssrf.assert_public_url",
        lambda url, resolve=True: (True, "ok"),
    )
    state = ve.start_view("x", gravity="G1")["view"]
    r = ve.record_search(state, query="serious critique query here", url="https://example.com/a")
    assert r["ok"] is False
    assert "placeholder" in r["reason"].lower() or "blocked" in r["reason"].lower()


def test_facade_has_view_and_refute():
    from godkiller_mcp.server import FACADE_ACTIONS

    assert FACADE_ACTIONS["gk_mode"]["view_start"] == "view_start"
    assert FACADE_ACTIONS["gk_mode"]["ultradeep_refute"] == "ultradeep_plan_refute"
