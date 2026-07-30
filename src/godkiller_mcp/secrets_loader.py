"""Secrets and environment variables loader for GODKILLER MCP."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def load_secrets(env_file: Optional[str | Path] = None) -> Dict[str, str]:
    secrets: Dict[str, str] = {}
    path = Path(env_file) if env_file else Path(".env")

    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#") and "=" in line_str:
                k, v = line_str.split("=", 1)
                secrets[k.strip()] = v.strip()
                os.environ[k.strip()] = v.strip()

    return secrets