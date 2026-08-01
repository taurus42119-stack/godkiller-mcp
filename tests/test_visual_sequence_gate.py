"""Multi-step visual QA sequence gate (Rule 8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.browser_bridge import BrowserEvidenceBridge
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, TaskKind
from godkiller_mcp.visual_sequence_gate import (
    DEFAULT_STEP_IDS,
    evaluate_visual_sequence,
    visual_sequence_claim_gate,
    watermark_elements_rejected,
)


def _nonblank_png(path: Path) -> None:
    from PIL import Image

    img = Image.new("RGB", (240, 240))
    px = img.load()
    for y in range(240):
        for x in range(240):
            px[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
    img.save(path)


def _open_feature(store: EvidenceStore, *, min_shots: int = 3):
    return store.open_task(
        TaskKind.FEATURE,
        "ui game visual feature",
        metadata={"visual_min_shots": min_shots, "require_visual_step_ids": True},
    )


def _submit_green(store: EvidenceStore, task_id: str, path: Path, step_id: str, label: str) -> None:
    store.submit_evidence(
        task_id=task_id,
        evidence_type=EvidenceType.LOG,
        summary=f"visual_critic GREEN {step_id}",
        payload={
            "source": "visual_critic",
            "verdict": "GREEN",
            "server_authored": True,
            "step_id": step_id,
            "vision": {
                "passed": True,
                "score": 0.95,
                "path": str(path),
                "expected_elements": [label],
                "elements_found": [label],
                "elements_missing": [],
                "ocr_engine": "mock",
            },
        },
        server_authored=True,
    )


def test_one_screenshot_blocks_claim(tmp_path: Path):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow missing")

    store = EvidenceStore(tmp_path / "ev")
    state = _open_feature(store, min_shots=3)
    browser = BrowserEvidenceBridge(store, artifact_dir=tmp_path / "ui")
    shot = tmp_path / "only.png"
    _nonblank_png(shot)
    browser.register_screenshot(state.handle.task_id, str(shot), step_id="01_boot", source="visual_step")

    ok, reason = visual_sequence_claim_gate(store.get(state.handle.task_id))
    assert ok is False
    assert "Visual sequence" in reason
    assert "≥3" in reason or "3" in reason


def test_ten_steps_green_passes_with_min3(tmp_path: Path):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow missing")

    store = EvidenceStore(tmp_path / "ev")
    min_shots = 3
    state = _open_feature(store, min_shots=min_shots)
    browser = BrowserEvidenceBridge(store, artifact_dir=tmp_path / "ui")
    steps = list(DEFAULT_STEP_IDS[:min_shots])
    labels = ["Sign in", "Invoice #42", "Submit"]
    tid = state.handle.task_id

    for sid, label in zip(steps, labels):
        path = tmp_path / f"{sid}.png"
        _nonblank_png(path)
        browser.register_screenshot(tid, str(path), step_id=sid, source="visual_step")
        _submit_green(store, tid, path, sid, label)

    report = evaluate_visual_sequence(store.get(tid))
    assert report["ok"] is True
    assert report["shots_count"] >= min_shots
    assert report["green_critic_count"] >= min_shots
    assert report["distinct_element_sets"] >= 3
    ok, _ = visual_sequence_claim_gate(store.get(tid))
    assert ok is True


def test_same_ocr_token_every_shot_fails_diversity(tmp_path: Path):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow missing")

    store = EvidenceStore(tmp_path / "ev")
    min_shots = 3
    state = _open_feature(store, min_shots=min_shots)
    browser = BrowserEvidenceBridge(store, artifact_dir=tmp_path / "ui")
    steps = list(DEFAULT_STEP_IDS[:min_shots])
    tid = state.handle.task_id

    for sid in steps:
        path = tmp_path / f"{sid}.png"
        _nonblank_png(path)
        browser.register_screenshot(tid, str(path), step_id=sid, source="visual_step")
        _submit_green(store, tid, path, sid, "Play")

    report = evaluate_visual_sequence(store.get(tid))
    assert report["ok"] is False
    assert report["distinct_element_sets"] == 1
    assert any("distinct expected_elements" in r for r in report["reasons"])


def test_watermark_only_claude_does_not_count_green(tmp_path: Path):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow missing")

    assert watermark_elements_rejected(["CLAUDE"]) is not None  # host chrome cheat token
    assert watermark_elements_rejected(["Sign in"]) is None

    store = EvidenceStore(tmp_path / "ev")
    min_shots = 3
    state = _open_feature(store, min_shots=min_shots)
    browser = BrowserEvidenceBridge(store, artifact_dir=tmp_path / "ui")
    steps = list(DEFAULT_STEP_IDS[:min_shots])
    tid = state.handle.task_id

    for sid in steps:
        path = tmp_path / f"{sid}.png"
        _nonblank_png(path)
        browser.register_screenshot(tid, str(path), step_id=sid, source="visual_step")
        _submit_green(store, tid, path, sid, "CLAUDE")

    report = evaluate_visual_sequence(store.get(tid))
    assert report["ok"] is False
    assert report["green_critic_count"] == 0


def test_require_ui_proof_uses_sequence(tmp_path: Path):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pytest.skip("Pillow missing")

    store = EvidenceStore(tmp_path / "ev")
    state = _open_feature(store, min_shots=2)
    browser = BrowserEvidenceBridge(store, artifact_dir=tmp_path / "ui")
    shot = tmp_path / "a.png"
    _nonblank_png(shot)
    browser.register_screenshot(state.handle.task_id, str(shot), step_id="01_boot")
    ok, reason = browser.require_ui_proof_for_feature(state.handle.task_id)
    assert ok is False
    assert "Visual sequence" in reason
