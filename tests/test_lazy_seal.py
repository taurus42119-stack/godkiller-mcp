"""P0: lazy seal — importing dispatch/server must not require GODKILLER_SEAL_KEY."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def test_import_dispatch_without_seal_subprocess():
    """Fresh interpreter: import must succeed with seal env unset."""
    env = os.environ.copy()
    for k in (
        "GODKILLER_SEAL_KEY",
        "GODKILLER_ALLOW_LEGACY_SEAL",
        "GODKILLER_SEAL_REQUIRE_ENV",
    ):
        env.pop(k, None)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    code = (
        "import godkiller_mcp.dispatch as d; "
        "import godkiller_mcp.server; "
        "assert d.store.__class__.__name__ == '_LazyProxy'; "
        "print('ok')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "ok" in r.stdout


def test_store_access_requires_seal(monkeypatch, tmp_path):
    monkeypatch.delenv("GODKILLER_SEAL_KEY", raising=False)
    monkeypatch.delenv("GODKILLER_ALLOW_LEGACY_SEAL", raising=False)
    monkeypatch.setenv("GODKILLER_HOME", str(tmp_path))
    from godkiller_mcp.dispatch import _LazyProxy
    from godkiller_mcp.evidence_store import EvidenceStore
    from godkiller_mcp.runtime_paths import tasks_dir

    lazy = _LazyProxy(lambda: EvidenceStore(persist_dir=tasks_dir(tmp_path)))
    with pytest.raises(RuntimeError, match="GODKILLER_SEAL_KEY|seal"):
        lazy.open_task(kind="bugfix", goal="x")
