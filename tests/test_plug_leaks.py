"""Leak-plug tests: blast AST, vision claim-grade, gate tokens, SSRF pin."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from godkiller_mcp.claim_verdict import build_claim_payload, classify_from_reason
from godkiller_mcp.code_intel import blast_radius
from godkiller_mcp.vision_bridge import VisionBridge


def test_blast_radius_ignores_comment_only(tmp_path: Path):
    (tmp_path / "only_comment.py").write_text("# helper foo is mentioned\n", encoding="utf-8")
    (tmp_path / "real.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    with patch("godkiller_mcp.code_intel._find_dev_binary", return_value=None):
        rep = blast_radius("foo", tmp_path)
    files = [Path(f).name for f in rep.files]
    assert "real.py" in files
    assert "only_comment.py" not in files
    assert rep.to_evidence_payload().get("engine") in ("python_ast", "ripgrep+ast")


def test_blast_radius_finds_call(tmp_path: Path):
    (tmp_path / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("from a import foo\nfoo()\n", encoding="utf-8")
    with patch("godkiller_mcp.code_intel._find_dev_binary", return_value=None):
        rep = blast_radius("foo", tmp_path)
    assert len(rep.files) >= 2


def test_blast_radius_regex_fallback_flag(tmp_path: Path):
    # Broken syntax → regex fallback when token appears
    (tmp_path / "broken.py").write_text("def foo(\n", encoding="utf-8")
    with patch("godkiller_mcp.code_intel._find_dev_binary", return_value=None):
        rep = blast_radius("foo", tmp_path)
    extra = rep.to_evidence_payload()
    assert extra.get("regex_fallback_used") is True
    assert "regex_fallback" in str(extra.get("engine") or "")
    assert extra.get("warn")
    assert "false positive" in str(extra.get("warn") or "").lower() or "regex" in str(
        extra.get("warn") or ""
    ).lower()
    assert "WARN:regex_fallback" in rep.summary


def test_vision_no_pil_never_claim_grade(tmp_path: Path, monkeypatch):
    import godkiller_mcp.vision_bridge as vb

    monkeypatch.setattr(vb, "HAS_PIL", False)
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG" + b"\x00" * 600)
    r = VisionBridge().analyze_screenshot(p)
    assert r.passed is False
    assert "size_only_not_claim_grade" in r.description or "OCR_UNAVAILABLE" in r.description


def test_classify_prefers_gate_token():
    assert classify_from_reason("something vague", gate="fault_probe") == "fault_probe"
    assert classify_from_reason("blocked gate=exit_checklist") == "exit"
    p = build_claim_payload(allowed=False, reason="nope", gate="swarm")
    assert p["gate"] == "swarm"
    assert p["status"] == "blocked"
