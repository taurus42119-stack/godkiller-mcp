"""
Scope-safe credentials loader.

Loads key=value pairs from a .env file into a localized dict without mutating
process os.environ. Initialization is lazy — import does not touch cwd/.env.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


class ScopeSafeSecretsLoader:
    """Loads credentials from .env without polluting global os.environ."""

    def __init__(self, env_path: Optional[Path] = None):
        self.env_path = env_path or (Path.cwd() / ".env")
        self._secrets: Dict[str, str] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.env_path.exists():
            return
        try:
            content = self.env_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    key = k.strip()
                    val = v.strip().strip("'\"")
                    if key and val:
                        self._secrets[key] = val
        except OSError:
            pass

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        self._ensure_loaded()
        return self._secrets.get(key, os.environ.get(key, default))

    def get_all_secrets(self) -> Dict[str, str]:
        self._ensure_loaded()
        return dict(self._secrets)


_global_loader: Optional[ScopeSafeSecretsLoader] = None


def _loader() -> ScopeSafeSecretsLoader:
    global _global_loader
    if _global_loader is None:
        _global_loader = ScopeSafeSecretsLoader()
    return _global_loader


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    return _loader().get_secret(key, default)


def load_localized_secrets(env_path: Optional[Path] = None) -> Dict[str, str]:
    return ScopeSafeSecretsLoader(env_path).get_all_secrets()
