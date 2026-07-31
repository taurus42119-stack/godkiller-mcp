"""Gauntlet suite — real pytest cases exercising kernel + engines the audit attacked."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from godkiller_mcp.code_intel import (
    CouncilDebateEngine,
    EpistemicConfidenceGate,
    ExhaustiveReaderEngine,
    PipelineRunner,
    SelfHealingEngine,
    check_edit_safe,
)
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, Phase
from godkiller_mcp.verify_bundle import detect_hacking
from godkiller_mcp.vision_bridge import VisionBridge
from godkiller_mcp.quality_gates import run_visual_critic


def test_exhaustive_reads_full_file_by_default(tmp_path: Path):
    big = "x" * 5000
    f = tmp_path / "big.py"
    f.write_text(big, encoding="utf-8")
    res = ExhaustiveReaderEngine().read_all(str(tmp_path), max_files=10)
    assert res["full_content"] is True
    assert len(res["contents"][str(f)]) == 5000
    assert res["truncated_files"] == []


def test_exhaustive_truncates_only_when_asked(tmp_path: Path):
    f = tmp_path / "big.py"
    f.write_text("y" * 5000, encoding="utf-8")
    res = ExhaustiveReaderEngine().read_all(str(tmp_path), max_chars_per_file=100)
    assert res["full_content"] is False
    assert len(res["contents"][str(f)]) == 100
    assert str(f) in res["truncated_files"]


def test_council_host_default_without_key(monkeypatch):
    monkeypatch.delenv("GODKILLER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    eng = CouncilDebateEngine()
    start = eng.debate("def add(a,b):\n    return a+b\n")
    assert start["mode"] == "host"
    assert start["verdict"] == "COUNCIL_IN_PROGRESS"
    sid = start["session_id"]
    for role in ("coder", "hacker", "optimizer"):
        eng.submit_opinion(sid, role, "APPROVE", critique=f"{role} ok", severity=1)
    fin = eng.finalize_host(sid)
    assert fin["consensus_reached"] is True
    assert fin["verdict"] == "COUNCIL_PASS"
    assert fin["mode"] == "host"


def test_council_host_incomplete_without_all_roles(monkeypatch):
    monkeypatch.delenv("GODKILLER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    eng = CouncilDebateEngine()
    start = eng.start_host("def x():\n    return 1\n")
    sid = start["session_id"]
    eng.submit_opinion(sid, "coder", "APPROVE", severity=1)
    fin = eng.finalize_host(sid)
    assert fin["verdict"] == "COUNCIL_INCOMPLETE"
    assert "hacker" in fin["missing_roles"]


def test_council_api_with_injected_chat():
    calls = {"n": 0}

    def fake_chat(system: str, user: str) -> str:
        calls["n"] += 1
        return json.dumps(
            {"vote": "APPROVE", "critique": "ok", "severity": 1, "must_fix": []}
        )

    good = "def add(a, b):\n    return a + b\n"
    r = CouncilDebateEngine().debate(good, mode="api", chat_fn=fake_chat, rounds=2)
    assert r["engine"] == "llm_multi_agent_council"
    assert r["mode"] == "api"
    assert calls["n"] == 6
    assert r["consensus_reached"] is True


def test_council_api_rejects_eval_via_hacker_and_static():
    def fake_chat(system: str, user: str) -> str:
        if "HACKER" in system:
            return json.dumps(
                {"vote": "REJECT", "critique": "eval is RCE", "severity": 10, "must_fix": ["remove eval"]}
            )
        return json.dumps({"vote": "APPROVE", "critique": "ok", "severity": 2, "must_fix": []})

    bad = "def f(x):\n    return eval(x)\n"
    r = CouncilDebateEngine().debate(bad, mode="api", chat_fn=fake_chat, rounds=2)
    assert r["consensus_reached"] is False
    assert r["hacker_veto"] is True or r["static_security_block"] is True
    assert r["verdict"] == "COUNCIL_REJECT"


def test_confidence_uses_ast_metrics(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text("def foo():\n    return 1\n\ndef bar():\n    return 2\n", encoding="utf-8")
    r = EpistemicConfidenceGate().evaluate(str(f), known_symbols=["foo", "bar"], has_searched=True, search_hit_count=3)
    assert r["engine"] == "edit_readiness_metrics"
    assert r["metrics"]["ast_parse_ok"] is True
    assert r["metrics"]["symbol_hit_rate"] == 1.0
    assert r["score"] >= 70
    assert "confidence_score" not in r or "checklist" not in r or r.get("metrics")


def test_pipeline_executes_real_handler():
    async def _run():
        calls = []

        async def executor(name, args):
            calls.append((name, args))
            return [{"type": "text", "text": "{}"}]

        # TextContent-like minimal
        class TC:
            def __init__(self, text):
                self.text = text

        async def executor2(name, args):
            calls.append((name, args))
            return [TC('{"ok": true}')]

        steps = [
            {"name": "godkiller_log_trace", "args": {"log_output": 'File "a.py", line 1, in x\n    z\nError: e'}},
            {"name": "godkiller_repo_map", "args": {"root_dir": "."}, "depends_on": [0]},
        ]
        res = await PipelineRunner().run_pipeline(steps, executor=executor2)
        assert res["dry_run"] is False
        assert all(s["status"] == "success" for s in res["results"])
        assert len(calls) == 2

    asyncio.run(_run())


def test_self_heal_executes_fallback():
    async def _run():
        class TC:
            def __init__(self, text):
                self.text = text

        async def executor(name, args):
            assert name == "godkiller_log_trace"
            return [TC('{"exception_type": "ValueError"}')]

        res = await SelfHealingEngine().heal_and_run(
            "other",
            "Traceback... ValueError: boom",
            executor=executor,
        )
        assert res["executed"] is True
        assert res["fallback_output"]["exception_type"] == "ValueError"

    asyncio.run(_run())


def test_verify_allowlist_not_five_word_ban():
    blocked, _ = detect_hacking("echo ok")
    assert blocked
    ok, reason = detect_hacking("python -m pytest -q")
    assert not ok, reason
    # TODO in command string must NOT block solely for containing TODO
    # (allowlist decides — pytest path is fine)
    ok2, _ = detect_hacking("pytest -q")
    assert not ok2


def test_vision_uses_expected_elements_fail_closed(tmp_path: Path):
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow missing")
    path = tmp_path / "ui.png"
    img = Image.new("RGB", (200, 200))
    px = img.load()
    for y in range(200):
        for x in range(200):
            px[x, y] = ((x * 7) % 256, (y * 11) % 256, (x * y) % 256)
    img.save(path)
    # No OCR / no sidecar → must fail when elements requested
    r = VisionBridge().analyze_screenshot(path, expected_elements=["Login", "Submit"])
    assert r.passed is False
    assert r.elements_missing == ["Login", "Submit"]

    sidecar = path.with_suffix(".txt")
    sidecar.write_text("Welcome Login Submit button", encoding="utf-8")
    r2 = VisionBridge().analyze_screenshot(path, expected_elements=["Login", "Submit"])
    assert r2.passed is True, r2.description
    assert set(r2.elements_found) == {"Login", "Submit"}


def test_visual_critic_uses_screenshot(tmp_path: Path):
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow missing")
    blank = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), color=(128, 128, 128)).save(blank)
    result = run_visual_critic(
        kind="feature",
        description="polished UI",
        checklist={
            "first_screen_readable": True,
            "not_placeholder": True,
            "materials_or_hierarchy_ok": True,
            "reference_delta_acceptable": True,
        },
        screenshot_path=str(blank),
    )
    assert result.verdict.value == "RED"
    payload = result.to_payload()
    assert "vision" in payload


def test_phase_and_forge_still_blocked(tmp_path: Path):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task("bugfix", "x")
    with pytest.raises(ValueError):
        store.assert_phase(state.handle.task_id, Phase.VERIFY)
    with pytest.raises(PermissionError):
        store.submit_evidence(state.handle.task_id, EvidenceType.PASSING_TEST, "nope", {})


def test_edit_safe_path_escape(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.py").write_text("1\n", encoding="utf-8")
    assert check_edit_safe(["a.py"], ws).payload["safe"] is True
    assert check_edit_safe(["../x.py"], ws).payload["safe"] is False
