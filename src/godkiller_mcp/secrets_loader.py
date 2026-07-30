"""
Scope-Safe Credentials & Secrets Loader
Loads credentials into a localized dictionary without polluting global process os.environ
"""

import os
from pathlib import Path
from typing import Dict, Optional


class ScopeSafeSecretsLoader:
    """Loads credentials from .env safely without polluting global os.environ"""

    def __init__(self, env_path: Optional[Path] = None):
        self.env_path = env_path or (Path.cwd() / ".env")
        self._secrets: Dict[str, str] = {}
        self._load_secrets()

    def _load_secrets(self) -> None:
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
        except Exception:
            pass

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Fetch secret from localized dictionary first, then fallback to os.environ safely"""
        return self._secrets.get(key, os.environ.get(key, default))

    def get_all_secrets(self) -> Dict[str, str]:
        """Returns localized dictionary copy without mutating process environment"""
        return dict(self._secrets)


_global_loader = ScopeSafeSecretsLoader()


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    return _global_loader.get_secret(key, default)


def load_localized_secrets(env_path: Optional[Path] = None) -> Dict[str, str]:
    return ScopeSafeSecretsLoader(env_path).get_all_secrets()