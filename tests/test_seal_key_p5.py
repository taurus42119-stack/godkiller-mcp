"""P5 seal key — host env preferred over workspace .seal_key."""

from __future__ import annotations

from pathlib import Path

import pytest

from godkiller_mcp.evidence_integrity import (
    attach_seal,
    load_or_create_seal_key,
    seal_status,
    verify_seal,
)
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, TaskKind


def test_env_seal_key_preferred_over_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "a" * 64)
    monkeypatch.delenv("GODKILLER_SEAL_REQUIRE_ENV", raising=False)
    persist = tmp_path / "tasks"
    persist.mkdir()
    # Poison file — must be ignored when env set
    (persist / ".seal_key").write_bytes(b"\x00" * 32)
    key = load_or_create_seal_key(persist)
    assert len(key) == 32
    # Same env → same key
    key2 = load_or_create_seal_key(persist)
    assert key == key2
    st = seal_status(persist)
    assert st["env_set"] is True
    assert st["source"] == "env"


def test_require_env_without_key_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.setenv("GODKILLER_SEAL_REQUIRE_ENV", "1")
    with pytest.raises(RuntimeError, match="GODKILLER_SEAL_KEY"):
        load_or_create_seal_key(tmp_path / "tasks")


def test_env_key_seals_and_verifies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "b" * 64)
    monkeypatch.delenv("GODKILLER_SEAL_REQUIRE_ENV", raising=False)
    store = EvidenceStore(persist_dir=tmp_path / "tasks")
    state = store.open_task(TaskKind.BUGFIX, "x")
    store.submit_evidence(
        state.handle.task_id,
        EvidenceType.LOG,
        "vb",
        {"source": "verify_bundle", "server_authored": True, "passed": True},
        server_authored=True,
    )
    ev = store.get(state.handle.task_id).evidences[-1]
    assert ev.payload.get("evidence_seal")
    assert verify_seal(state.handle.task_id, ev.payload, store._seal_key)


def test_passphrase_env_derives_stable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_SEAL_KEY", "host-secret-passphrase")
    k1 = load_or_create_seal_key(tmp_path / "a")
    k2 = load_or_create_seal_key(tmp_path / "b")
    assert k1 == k2
    assert len(k1) == 32


def test_ship_profile_requires_env_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.delenv("GODKILLER_SEAL_REQUIRE_ENV", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_LEGACY_SEAL", raising=False)
    with pytest.raises(RuntimeError, match="GODKILLER_SEAL_KEY|docs/SEAL_KEY"):
        load_or_create_seal_key(tmp_path / "ship_tasks")


def test_default_does_not_mint_seal_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.delenv("GODKILLER_SEAL_REQUIRE_ENV", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_LEGACY_SEAL", raising=False)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    persist = tmp_path / "tasks"
    persist.mkdir()
    with pytest.raises(RuntimeError, match="will not be auto-created|SEAL_KEY"):
        load_or_create_seal_key(persist)
    assert not (persist / ".seal_key").exists()


def test_legacy_seal_requires_allow_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.delenv("GODKILLER_SEAL_REQUIRE_ENV", raising=False)
    monkeypatch.delenv("GODKILLER_PROFILE", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_LEGACY_SEAL", raising=False)
    persist = tmp_path / "tasks"
    persist.mkdir()
    (persist / ".seal_key").write_bytes(b"\x11" * 32)
    with pytest.raises(RuntimeError, match="ALLOW_LEGACY|disabled"):
        load_or_create_seal_key(persist)

    monkeypatch.setenv("GODKILLER_ALLOW_LEGACY_SEAL", "1")
    key = load_or_create_seal_key(persist)
    assert key == b"\x11" * 32


def test_ship_ignores_allow_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_PROFILE", "ship")
    monkeypatch.setenv("GODKILLER_ALLOW_LEGACY_SEAL", "1")
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    persist = tmp_path / "tasks"
    persist.mkdir()
    (persist / ".seal_key").write_bytes(b"\x22" * 32)
    with pytest.raises(RuntimeError, match="GODKILLER_SEAL_KEY|ship"):
        load_or_create_seal_key(persist)
