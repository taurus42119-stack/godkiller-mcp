"""Skills Registry: Local and marketplace skill loader for GODKILLER MCP."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


class SkillsRegistry:
    def __init__(self, skills_dir: Optional[str | Path] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path(".agents/skills")

    def list_skills(self) -> List[str]:
        if not self.skills_dir.exists():
            return []
        return [
            d.name
            for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ]

    def get_skill_path(self, skill_name: str) -> Optional[Path]:
        path = self.skills_dir / skill_name / "SKILL.md"
        return path if path.exists() else None
