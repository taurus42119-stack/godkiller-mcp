"""P1: sealed tasks under arena-style GODKILLER_HOME score process dims."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.score_11 import sealed_artifact_signals
from godkiller_mcp.evidence_integrity import attach_seal
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, Phase


def test_arm_home_store_mints_scorable_sealed_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """WITH arm pattern: GODKILLER_HOME=<arm>/.godkiller + shared SEAL_KEY."""
    key_hex = "cd" * 32
    monkeypatch.setenv("GODKILLER_SEAL_KEY", key_hex)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    arm = tmp_path / "2_WITH_MCP"
    home = arm / ".godkiller"
    tasks = home / "tasks"
    tasks.mkdir(parents=True)

    store = EvidenceStore(persist_dir=tasks)
    state = store.open_task(kind="feature", goal="prove process dims")
    tid = state.handle.task_id
    secret = store._seal_key
    assert secret is not None

    store.submit_evidence(
        tid,
        EvidenceType.BLAST_RADIUS,
        "blast",
        {"server_authored": True, "symbol": "main"},
        server_authored=True,
    )
    store.submit_evidence(
        tid,
        EvidenceType.EDIT_SAFE,
        "edit",
        {"server_authored": True, "paths": ["src/a.py"]},
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
        },
        server_authored=True,
    )
    for src in (
        "verify_bundle",
        "exit_checklist",
        "council_finalize",
        "fault_probe",
        "visual_critic",
    ):
        payload = attach_seal(
            tid,
            {
                "source": src,
                "server_authored": True,
                "passed": True,
                **(
                    {"verdict": "GREEN", "vision": {"passed": True, "expected_elements": ["OK"]}}
                    if src == "visual_critic"
                    else {}
                ),
            },
            secret,
        )
        store.submit_evidence(
            tid, EvidenceType.LOG, src, payload, server_authored=True
        )

    store.update_metadata(tid, {"chosen_design": "A", "plan_os": True})
    store.assert_phase(tid, Phase.REPRODUCE)

    assert list(tasks.glob("*.json"))

    sig = sealed_artifact_signals(arm)
    lit = sum(
        1
        for k in (
            "exhaustive_read",
            "blast_radius",
            "edit_safe",
            "verify_bundle",
            "council",
            "security",
            "visual_critic",
        )
        if sig.get(k)
    )
    assert lit >= 3, sig


def test_handlers_registry_populated():
    from godkiller_mcp.handlers import REGISTRY, ensure_registered

    ensure_registered()
    assert "open_task" in REGISTRY
    assert "verify_bundle" in REGISTRY
    assert "check_edit_safe" in REGISTRY
    assert "godkiller_auto_fix" in REGISTRY
    assert len(REGISTRY) >= 40
