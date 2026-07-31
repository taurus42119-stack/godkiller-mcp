"""Smoke tests for Antigravity A/B helpers — sealed dims 5–11."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmarks.score_11 import (
    DIMENSIONS,
    score_dimensions,
    sealed_artifact_signals,
)
from godkiller_mcp.evidence_integrity import attach_seal, load_or_create_seal_key


def test_eleven_dimensions_defined():
    assert len(DIMENSIONS) == 11


def test_header_only_zeroes_overall():
    oracle = {
        "counts": {"passed": 10, "failed": 0, "skipped": 0, "collected": 10},
        "has_body": False,
        "header_only": True,
    }
    delta = {"pct": 100.0, "changed_files": 6, "total_files": 6, "details": []}
    signals = {
        k: True
        for k in (
            "exhaustive_read",
            "open_task",
            "plan_os",
            "blast_radius",
            "edit_safe",
            "verify_bundle",
            "claim_done",
            "council",
            "security",
            "visual_critic",
            "screenshot_count",
            "marathon",
            "hay_chars",
        )
    }
    dims, meta = score_dimensions(oracle, delta, signals)
    assert meta["overall_score"] == 0.0
    assert dims["3_output_integrity"] == 0.0


def test_full_body_can_score():
    oracle = {
        "counts": {"passed": 516, "failed": 0, "skipped": 0, "collected": 516},
        "has_body": True,
        "header_only": False,
    }
    delta = {"pct": 100.0, "changed_files": 6, "total_files": 6, "details": []}
    signals = {
        "exhaustive_read": True,
        "open_task": True,
        "plan_os": True,
        "blast_radius": True,
        "edit_safe": True,
        "verify_bundle": True,
        "claim_done": True,
        "council": True,
        "security": True,
        "visual_critic": True,
        "screenshot_count": 1,
        "marathon": True,
        "hay_chars": 100,
    }
    dims, meta = score_dimensions(oracle, delta, signals)
    assert dims["1_code_correctness"] == 100.0
    assert meta["overall_score"] == 100.0


def test_haystack_forge_without_seal_scores_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_LEGACY_SEAL", raising=False)
    gk = tmp_path / ".godkiller" / "tasks"
    gk.mkdir(parents=True)
    (gk / "notes.md").write_text(
        "exhaustive full_content verify_bundle council hacker visual_critic anti-slop\n",
        encoding="utf-8",
    )
    (tmp_path / "shot.png").write_bytes(b"\x89PNG\r\n" + b"\x00" * 64)
    sig = sealed_artifact_signals(tmp_path)
    assert sig["sealed"] is False
    oracle = {
        "counts": {"passed": 516, "failed": 0, "skipped": 0, "collected": 516},
        "has_body": True,
        "header_only": False,
    }
    delta = {"pct": 50.0, "changed_files": 3, "total_files": 6, "details": []}
    dims, _ = score_dimensions(oracle, delta, sig)
    for k in (
        "5_reconnaissance_read",
        "6_phase_discipline",
        "7_blast_edit_safe",
        "8_verify_claim_gate",
        "9_council_review",
        "10_security_hardening",
        "11_ui_visual_gate",
    ):
        assert dims[k] == 0.0, k


def test_sealed_fixture_scores_armor_dims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    key_hex = "ab" * 32
    monkeypatch.setenv("GODKILLER_SEAL_KEY", key_hex)
    secret = load_or_create_seal_key(tmp_path / ".godkiller" / "tasks")
    tid = "task_seal_fixture"
    tasks = tmp_path / ".godkiller" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)

    def _armor(source: str, extra: dict | None = None) -> dict:
        payload = {"source": source, "server_authored": True, "passed": True}
        if extra:
            payload.update(extra)
        return attach_seal(tid, payload, secret)

    evidences = [
        {
            "type": "blast_radius",
            "payload": {"server_authored": True, "symbol": "x"},
        },
        {
            "type": "edit_safe",
            "payload": {"server_authored": True, "paths": ["a.py"]},
        },
        {
            "type": "log",
            "payload": {
                "server_authored": True,
                "engine": "exhaustive_reader_engine",
                "full_content": True,
            },
        },
        {"type": "log", "payload": _armor("verify_bundle")},
        {"type": "log", "payload": _armor("exit_checklist")},
        {"type": "log", "payload": _armor("council_finalize")},
        {"type": "log", "payload": _armor("fault_probe")},
        {
            "type": "log",
            "payload": _armor(
                "visual_critic",
                {"verdict": "GREEN", "vision": {"passed": True, "expected_elements": ["OK"]}},
            ),
        },
    ]
    doc = {
        "handle": {
            "task_id": tid,
            "phase": "claim_done",
            "metadata": {"chosen_design": "A"},
        },
        "phase_history": ["open", "reproduce", "verify", "claim_done"],
        "evidences": evidences,
    }
    (tasks / f"{tid}.json").write_text(json.dumps(doc), encoding="utf-8")
    (tmp_path / ".godkiller" / "marathon_run").mkdir(parents=True, exist_ok=True)

    sig = sealed_artifact_signals(tmp_path)
    assert sig["sealed"] is True
    assert sig["verify_bundle"] is True
    assert sig["council"] is True
    assert sig["security"] is True
    assert sig["visual_critic"] is True
    assert sig["blast_radius"] is True
    assert sig["edit_safe"] is True
    assert sig["exhaustive_read"] is True

    oracle = {
        "counts": {"passed": 516, "failed": 0, "skipped": 0, "collected": 516},
        "has_body": True,
        "header_only": False,
    }
    delta = {"pct": 100.0, "changed_files": 6, "total_files": 6, "details": []}
    dims, meta = score_dimensions(oracle, delta, sig)
    assert dims["7_blast_edit_safe"] == 100.0
    assert dims["8_verify_claim_gate"] == 100.0
    assert dims["9_council_review"] == 100.0
    assert dims["10_security_hardening"] == 100.0
    assert dims["11_ui_visual_gate"] == 100.0
    assert dims["5_reconnaissance_read"] == 100.0
    assert meta["overall_score"] > 0


def test_forged_armor_source_without_valid_seal_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "cd" * 32)
    tasks = tmp_path / ".godkiller" / "tasks"
    tasks.mkdir(parents=True)
    tid = "task_forge"
    doc = {
        "handle": {"task_id": tid, "phase": "verify"},
        "phase_history": ["open"],
        "evidences": [
            {
                "type": "log",
                "payload": {
                    "source": "verify_bundle",
                    "server_authored": True,
                    "passed": True,
                    "evidence_seal": "deadbeef" * 8,
                },
            },
            {
                "type": "log",
                "payload": {
                    "source": "visual_critic",
                    "server_authored": True,
                    "verdict": "GREEN",
                    "evidence_seal": "00" * 32,
                },
            },
        ],
    }
    (tasks / f"{tid}.json").write_text(json.dumps(doc), encoding="utf-8")
    sig = sealed_artifact_signals(tmp_path)
    assert sig["verify_bundle"] is False
    assert sig["visual_critic"] is False
