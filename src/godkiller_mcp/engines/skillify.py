"""Engine extracted from code_intel god-module."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

class AutoSkillifyEngine:
    """Generates reusable SKILL.md in .agents/skills/<skill_name>/ upon task completion."""

    def skillify(
        self,
        skill_name: str,
        description: str,
        instructions: str,
        workspace_root: str = ".",
    ) -> Dict[str, Any]:
        root = Path(workspace_root).resolve()
        skill_dir = root / ".agents" / "skills" / skill_name
        skill_file = skill_dir / "SKILL.md"
        from godkiller_mcp.code_intel import check_edit_safe
        gate = check_edit_safe([str(skill_file)], root)
        if not gate.payload.get("safe"):
            return {
                "engine": "auto_skillify_engine",
                "skill_name": skill_name,
                "status": "blocked",
                "error": "check_edit_safe blocked write",
                "edit_safe": gate.payload,
            }

        skill_dir.mkdir(parents=True, exist_ok=True)

        content = f"""---
name: {skill_name}
description: {description}
---

# {skill_name.replace('-', ' ').title()}

## Overview
{description}

## Instructions & Protocol
{instructions}
"""
        skill_file.write_text(content, encoding="utf-8")
        return {
            "engine": "auto_skillify_engine",
            "skill_name": skill_name,
            "file": str(skill_file),
            "status": "created",
            "edit_safe": gate.payload,
        }
