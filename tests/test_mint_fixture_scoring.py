"""Mint fixtures must not light earned process dims."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.score_11 import sealed_artifact_signals
from godkiller_mcp.evidence_integrity import attach_seal
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, Phase


def test_mint_fixture_excluded_from_earned_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    key_hex = "ef" * 32
    monkeypatch.setenv("GODKILLER_SEAL_KEY", key_hex)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    arm = tmp_path / "2_WITH_MCP"
    tasks = arm / ".godkiller" / "tasks"
    tasks.mkdir(parents=True)

    store = EvidenceStore(persist_dir=tasks)
    secret = store._seal_key
    assert secret is not None
    state = store.open_task(kind="feature", goal="mint only")
    tid = state.handle.task_id
    mint = {"provenance": "mint_fixture", "minted": True}

    store.submit_evidence(
        tid,
        EvidenceType.BLAST_RADIUS,
        "blast",
        {"server_authored": True, "symbol": "x", **mint},
        server_authored=True,
    )
    store.submit_evidence(
        tid,
        EvidenceType.EDIT_SAFE,
        "edit",
        {"server_authored": True, "paths": ["a.py"], **mint},
        server_authored=True,
    )
    store.submit_evidence(
        tid,
        EvidenceType.LOG,
        "exhaustive",
        {
            "server_authored": True,
            "engine": "exhaustive_reader_engine",
            "full_content": True,
            **mint,
        },
        server_authored=True,
    )
    for src in ("verify_bundle", "exit_checklist", "council_finalize", "fault_probe", "visual_critic"):
        payload = attach_seal(
            tid,
            {
                "source": src,
                "server_authored": True,
                "passed": True,
                **mint,
                **(
                    {"verdict": "GREEN", "vision": {"passed": True, "expected_elements": ["OK"]}}
                    if src == "visual_critic"
                    else {}
                ),
            },
            secret,
        )
        store.submit_evidence(tid, EvidenceType.LOG, src, payload, server_authored=True)
    store.update_metadata(
        tid, {"chosen_design": "A", "plan_os": True, "provenance": "mint_fixture", "minted": True}
    )
    store.assert_phase(tid, Phase.REPRODUCE)
    store.mark_closed(tid)

    sig = sealed_artifact_signals(arm)
    assert sig["minted_task_files"] == 1
    assert sig["minted_process_lit"] is True
    assert sig["exhaustive_read"] is False
    assert sig["blast_radius"] is False
    assert sig["edit_safe"] is False
    assert sig["verify_bundle"] is False
    assert sig["council"] is False
    assert sig["security"] is False
    assert sig["visual_critic"] is False
    assert "verify_bundle" in sig["minted_sealed_sources"]
