"""Force swarm: server auto scout + edit gate — no canned attacker."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.swarm import collect_swarm, require_swarm_before_edit, spawn_swarm, submit_role


def test_server_auto_fills_scout_not_attacker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_PROFILE", "default")
    monkeypatch.setenv("GODKILLER_SWARM_AUTO", "1")
    (tmp_path / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    out = spawn_swarm("fix hello.py module", workspace=str(tmp_path), mode="host")
    assert out.get("server_auto_roles")
    assert "scout" in (out.get("server_auto_roles") or [])
    assert "attacker" not in (out.get("server_auto_roles") or [])
    assert out.get("phase") == "awaiting_roles"
    col = collect_swarm(out["session_id"])
    assert col.get("passed") is False


def test_host_attacker_then_collect_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_SWARM_AUTO", "1")
    (tmp_path / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    out = spawn_swarm("fix hello.py module", workspace=str(tmp_path), mode="host")
    sid = out["session_id"]
    scout_paths = (out.get("scout_auto") or {}).get("paths") or ["hello.py"]
    path0 = scout_paths[0] if scout_paths else "hello.py"
    submit_role(
        sid,
        "attacker",
        {
            "findings": [
                f"Unchecked error paths in {path0} may hide failing cases before claim."
            ],
            "must_fix": ["Add failing test covering the broken hello path"],
            "vote": "REJECT",
            "severity": 6,
            "paths": [path0],
        },
    )
    col = collect_swarm(sid)
    assert col.get("passed") is True, col


def test_canned_server_attacker_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_SWARM_AUTO", "0")
    out = spawn_swarm("fix login", workspace=str(tmp_path), mode="host")
    sid = out["session_id"]
    for role, payload in (
        ("scout", {"findings": ["auth module in app.py"], "paths": ["app.py"]}),
        (
            "attacker",
            {
                "findings": ["Server attacker: refuse claim without disk verify"],
                "must_fix": ["Remove stub copy and untested branches before claim"],
                "vote": "REJECT",
                "paths": ["app.py"],
            },
        ),
        ("planner", {"steps": ["patch app.py"], "paths": ["app.py"]}),
        ("verifier", {"commands": ["python -m pytest -q"], "checks": ["login test"]}),
    ):
        submit_role(sid, role, payload)
    col = collect_swarm(sid)
    assert col.get("passed") is False
    assert "canned" in (col.get("reason") or "").lower() or "stub" in (col.get("reason") or "").lower()


def test_require_swarm_blocks_edit_without_collect(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)

    class _H:
        metadata = {"require_swarm": True}

    class _S:
        handle = _H()
        evidences = []

    ok, reason = require_swarm_before_edit(_S())
    assert ok is False
    assert "swarm" in reason.lower()
