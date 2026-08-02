"""P0: write_allow cannot rebind jail; verify children do not inherit SEAL_KEY."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from godkiller_mcp.safe_exec import run_command_safely, scrubbed_environ
from godkiller_mcp.write_guard import decide_from_hook_event, persist_allow_paths


@pytest.fixture(autouse=True)
def _seal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "ab" * 32)
    monkeypatch.setenv("GODKILLER_WORKSPACE", str(tmp_path / "pin"))
    monkeypatch.setenv("GODKILLER_HOME", str(tmp_path / "home"))
    (tmp_path / "pin").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path / "pin")


def test_scrubbed_environ_drops_seal(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "deadbeef" * 8)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))
    env = scrubbed_environ()
    assert "GODKILLER_SEAL_KEY" not in env
    assert "OPENAI_API_KEY" not in env
    assert "PATH" in env


def test_safe_exec_child_cannot_read_seal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    import sys

    monkeypatch.setenv("GODKILLER_SEAL_KEY", "cd" * 32)
    pin = tmp_path / "pin"
    script = pin / "probe_seal.py"
    script.write_text(
        "import os, sys\n"
        "sys.exit(0 if not os.environ.get('GODKILLER_SEAL_KEY') else 64)\n",
        encoding="utf-8",
    )
    proc = run_command_safely([sys.executable, str(script)], cwd=pin, timeout_sec=15)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_write_allow_cannot_rebind_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pin = tmp_path / "pin"
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secrets.txt"
    secret.write_text("LEAK\n", encoding="utf-8")

    # Forge envelope sealed for wider workspace (attacker parent)
    # Using persist under outside then copy into pin .godkiller with wrong workspace field
    persist_allow_paths(outside, ["secrets.txt"], task_id="t1")
    forged = json.loads((outside / ".godkiller" / "write_allow.json").read_text(encoding="utf-8"))
    # Place forged envelope inside pin tree (where hook looks relative to auth ws)
    dest = pin / ".godkiller"
    dest.mkdir(parents=True, exist_ok=True)
    # Keep HMAC for outside workspace — verify may fail OR seal matches outside
    # Attack from critique: after HMAC, code used to set ws = data["workspace"]
    (dest / "write_allow.json").write_text(json.dumps(forged), encoding="utf-8")

    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(secret)},
        "cwd": str(pin),
    }
    decision = decide_from_hook_event(event, workspace=str(pin))
    assert decision["permissionDecision"] == "deny"
    assert decision.get("allowed") is False


def test_matching_envelope_still_allows_under_pin(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    pin = tmp_path / "pin"
    (pin / "ok.py").write_text("x=1\n", encoding="utf-8")
    persist_allow_paths(pin, ["ok.py"], task_id="t2")
    event = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(pin / "ok.py")},
        "cwd": str(pin),
    }
    decision = decide_from_hook_event(event, workspace=str(pin))
    assert decision["permissionDecision"] == "allow"
