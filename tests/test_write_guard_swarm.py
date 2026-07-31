"""write_guard + swarm — real enforcement, no mock executed:false."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import TaskKind
from godkiller_mcp.swarm import collect_swarm, claim_swarm_gate, spawn_swarm, submit_role
from godkiller_mcp.write_guard import decide_write, persist_allow_paths


def test_write_guard_denies_outside_allowlist(tmp_path: Path):
    (tmp_path / "ok.py").write_text("x=1\n", encoding="utf-8")
    d = decide_write(path="evil.py", workspace=tmp_path, allow_paths=["ok.py"])
    assert d["allowed"] is False
    assert d["permissionDecision"] == "deny"


def test_write_guard_allows_listed_path(tmp_path: Path):
    d = decide_write(path="ok.py", workspace=tmp_path, allow_paths=["ok.py"])
    assert d["allowed"] is True


def test_write_guard_denies_outside_workspace(tmp_path: Path):
    d = decide_write(path="C:/Windows/notepad.exe", workspace=tmp_path, allow_paths=["a.py"])
    assert d["allowed"] is False


def test_write_guard_cli_exit_2_on_deny(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(tmp_path / "nope.py")},
        "cwd": str(tmp_path),
    }
    persist_allow_paths(tmp_path, ["only.py"])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        __import__("io").StringIO(json.dumps(event)),
    )
    from godkiller_mcp.write_guard import main

    code = main(["--stdin"])
    assert code == 2


def test_write_guard_install_hint_and_copy(tmp_path: Path, capsys):
    from godkiller_mcp.write_guard import main

    code = main(["install-hint", "--workspace", str(tmp_path)])
    assert code == 0
    hint = json.loads(capsys.readouterr().out)
    assert hint["ok"] is True
    assert "godkiller-write-guard --stdin" in hint["command"]

    code = main(["install", "--workspace", str(tmp_path), "--target", "cursor"])
    assert code == 0
    installed = json.loads(capsys.readouterr().out)
    dest = Path(installed["copied"])
    assert dest.is_file()
    assert "Write" in dest.read_text(encoding="utf-8")
    # no overwrite without --force
    code = main(["install", "--workspace", str(tmp_path), "--target", "cursor"])
    assert code == 1


def test_swarm_host_collect_requires_attacker(tmp_path: Path):
    out = spawn_swarm("fix login", workspace=str(tmp_path), mode="host")
    sid = out["session_id"]
    submit_role(sid, "scout", {"findings": ["auth module in app.py"], "paths": ["app.py"]})
    submit_role(sid, "planner", {"steps": ["patch app.py"], "paths": ["app.py"]})
    submit_role(sid, "verifier", {"commands": ["python -m pytest -q"], "checks": ["login test"]})
    # attacker empty
    submit_role(sid, "attacker", {"findings": [], "vote": "OK"})
    collected = collect_swarm(sid)
    assert collected["passed"] is False


def test_swarm_collect_pass_and_claim_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_DEV_RELAX", raising=False)
    monkeypatch.setenv("GODKILLER_SWARM_REQUIRED", "1")
    out = spawn_swarm("fix login", workspace=str(tmp_path), mode="host", task_id="t1")
    sid = out["session_id"]
    submit_role(sid, "scout", {"findings": ["auth in app.py"], "paths": ["app.py"]})
    submit_role(
        sid,
        "attacker",
        {
            "findings": ["session fixation risk in app.py login handler without rotate"],
            "must_fix": ["rotate session id after password change"],
            "vote": "REJECT",
            "paths": ["app.py"],
        },
    )
    submit_role(sid, "planner", {"steps": ["fix session"], "paths": ["app.py"]})
    submit_role(sid, "verifier", {"commands": ["python -m pytest -q"], "checks": ["test_login"]})
    collected = collect_swarm(sid)
    assert collected["passed"] is True, collected

    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "fix")
    store.update_metadata(state.handle.task_id, {"require_swarm": True})
    store.submit_evidence(
        state.handle.task_id,
        "log",
        "swarm",
        {**collected, "source": "swarm_collect", "server_authored": True},
        server_authored=True,
    )
    ok, reason = claim_swarm_gate(store.get(state.handle.task_id))
    assert ok is True, reason


def test_facade_has_guard_and_swarm():
    from godkiller_mcp.server import FACADE_ACTIONS

    assert FACADE_ACTIONS["gk_guard"]["write"] == "write_guard"
    assert FACADE_ACTIONS["gk_code"]["swarm_spawn"] == "swarm_spawn"
