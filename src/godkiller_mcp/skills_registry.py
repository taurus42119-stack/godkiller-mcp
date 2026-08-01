"""Skills Registry: Local and marketplace skill loader for GODKILLER MCP."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from godkiller_mcp.skill_catalog import build_catalog, resolve_skill_roots


class SkillsRegistry:
    def __init__(self, skills_dir: Optional[str | Path] = None):
        self.skills_dir = Path(skills_dir) if skills_dir else Path(".agents/skills")

    def list_skills(self) -> List[str]:
        roots = resolve_skill_roots(self.skills_dir.parent if self.skills_dir.name == "skills" else None)
        if self.skills_dir.is_dir() and self.skills_dir not in roots:
            roots = [self.skills_dir, *roots]
        names = sorted({e["name"] for e in build_catalog(roots)})
        return names

    def get_skill_path(self, skill_name: str) -> Optional[Path]:
        roots = resolve_skill_roots()
        if self.skills_dir.is_dir():
            roots = [self.skills_dir, *roots]
        for e in build_catalog(roots):
            if e.get("name") == skill_name:
                return Path(e["path"])
        path = self.skills_dir / skill_name / "SKILL.md"
        return path if path.exists() else None
