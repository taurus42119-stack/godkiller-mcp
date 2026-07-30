from __future__ import annotations

from pathlib import Path

from godkiller_mcp.secrets_loader import ScopeSafeSecretsLoader


def test_secrets_loader_does_not_mutate_environ(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DEMO_SECRET=super-secret\n", encoding="utf-8")
    monkeypatch.delenv("DEMO_SECRET", raising=False)

    loader = ScopeSafeSecretsLoader(env_file)
    assert loader.get_secret("DEMO_SECRET") == "super-secret"
    assert "DEMO_SECRET" not in __import__("os").environ
    assert loader.get_all_secrets() == {"DEMO_SECRET": "super-secret"}
