"""Durable marathon relay state persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class DurableMarathonStore:
    def __init__(self, marathon_dir: str | Path):
        self.marathon_dir = Path(marathon_dir)
        self.marathon_dir.mkdir(parents=True, exist_ok=True)

    def _state_file(self, slug: str) -> Path:
        return self.marathon_dir / f"{slug}_durable_state.json"

    def save(self, slug: str, state_data: Dict[str, Any]) -> None:
        path = self._state_file(slug)
        path.write_text(json.dumps(state_data, indent=2), encoding="utf-8")

    def load(self, slug: str) -> Optional[Dict[str, Any]]:
        path = self._state_file(slug)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
