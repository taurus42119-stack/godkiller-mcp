"""Skill Catalog: Look-then-choose skill discovery engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


def build_catalog(skills_dir: str | Path) -> List[Dict[str, Any]]:
    skills_path = Path(skills_dir)
    catalog: List[Dict[str, Any]] = []

    if skills_path.exists():
        for skill_md in skills_path.rglob("SKILL.md"):
            try:
                content = skill_md.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(skill_md)
                name = skill_md.parent.name

                desc = ""
                for line in content.splitlines():
                    if line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip()
                        break

                catalog.append(
                    {
                        "name": name,
                        "path": rel_path,
                        "description": desc or content[:100],
                    }
                )
            except Exception:
                pass

    return catalog


def filter_catalog(
    catalog: Dict[str, Any] | List[Dict[str, Any]], query: str, limit: int = 20
) -> List[Dict[str, Any]]:
    if isinstance(catalog, dict):
        entries = list(catalog.values())
    else:
        entries = catalog

    if not query:
        return entries[:limit]

    q_lower = query.lower()
    matched = []

    for item in entries:
        name = item.get("name", "")
        desc = item.get("description", "")
        path = item.get("path", "")
        if q_lower in name.lower() or q_lower in desc.lower() or q_lower in path.lower():
            matched.append(item)

    return matched[:limit] if matched else entries[:limit]


def suggest_from_catalog(
    catalog: Dict[str, Any] | List[Dict[str, Any]],
    goal: str,
    limit: int = 4,
    forced_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    hits = filter_catalog(catalog, goal, limit=limit)
    shortlist_paths: List[str] = [item["path"] for item in hits if "path" in item]

    if forced_paths:
        for p in forced_paths:
            if p not in shortlist_paths:
                shortlist_paths.insert(0, p)

    return {
        "shortlist": hits[:limit],
        "shortlist_paths": shortlist_paths[:limit],
        "suggested_skills": hits[:limit],
        "rule": "view_file at most 2–4 SKILL.md paths you pick",
    }
