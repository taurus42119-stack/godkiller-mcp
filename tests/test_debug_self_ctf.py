""" /debug Self-CTF — workspace-only adversarial loop."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.debug_engine import require_self_ctf_before_fix, run_until, start, tick


def test_self_ctf_tick_finds_local_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    # Plant a classic pattern security scan / search can hit
    (tmp_path / "bad.py").write_text(
        "password = 'secret123'\neval(user_input)\n",
        encoding="utf-8",
    )
    out = start(workspace=str(tmp_path), goal="find eval password bugs", max_rounds=3)
    assert out["ok"] is True
    ctf = out["ctf"]
    # tick until findings or cap
    last = None
    for _ in range(3):
        last = tick(ctf)
        ctf = last["ctf"]
        if ctf.get("findings"):
            break
    assert ctf.get("findings"), last
    assert ctf.get("scope") == "workspace_only"


def test_self_ctf_run_until_stops_on_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    (tmp_path / "bad.py").write_text(
        "password = 'secret123'\neval(user_input)\n",
        encoding="utf-8",
    )
    started = start(workspace=str(tmp_path), goal="find eval password bugs", max_rounds=5)
    out = run_until(started["ctf"], link_fault_probe=False)
    assert out["ok"] is True
    assert out["source"] == "debug_self_ctf_run_until"
    assert out["ctf"].get("findings")
    assert out["rounds_run"] >= 1
    assert out["rounds_run"] <= 5


def test_require_blocks_without_findings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)

    class _H:
        metadata = {"mode": "debug", "require_self_ctf": True}

    class _S:
        handle = _H()

        def evidence_types(self):
            return []

    ok, reason = require_self_ctf_before_fix(_S())
    assert ok is False
    assert "Self-CTF" in reason or "self_ctf" in reason.lower()
