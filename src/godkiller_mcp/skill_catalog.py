"""Skill Catalog: Look-then-choose skill discovery engine (multi-root)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from godkiller_mcp.runtime_paths import package_root


CatalogEntry = Dict[str, Any]
CatalogInput = Union[Dict[str, Any], List[Dict[str, Any]]]


def resolve_skill_roots(agents_root: str | Path | None = None) -> List[Path]:
    """Ordered unique skill roots: workspace .agents, package .agents, bundled agent-ops."""
    roots: List[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key in seen or not p.is_dir():
            return
        seen.add(key)
        roots.append(p)

    env = os.environ.get("GODKILLER_SKILLS_ROOTS", "").strip()
    if env:
        for part in env.replace(";", os.pathsep).split(os.pathsep):
            part = part.strip()
            if part:
                _add(Path(part))

    if agents_root:
        _add(Path(agents_root) / "skills")

    cwd_agents = Path.cwd() / ".agents" / "skills"
    _add(cwd_agents)

    # Parent workspace (arena often cwd=arm; skills live on Desktop repo)
    parent = Path.cwd().parent
    for _ in range(4):
        _add(parent / ".agents" / "skills")
        if parent.parent == parent:
            break
        parent = parent.parent

    pkg = package_root()
    _add(pkg / ".agents" / "skills")
    _add(Path(__file__).resolve().parent / "bundled_skills")

    return roots


def _index_skill_md(skill_md: Path, source_root: Path) -> Optional[CatalogEntry]:
    try:
        content = skill_md.read_text(encoding="utf-8", errors="ignore")
        name = skill_md.parent.name
        desc = ""
        for line in content.splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip().strip(">").strip()
                break
            if line.startswith("name:") and not desc:
                pass
        # Prefer path relative to source root when possible
        try:
            rel = str(skill_md.resolve().relative_to(source_root.resolve()))
            path_out = str((source_root / rel).resolve())
        except ValueError:
            path_out = str(skill_md.resolve())
        # Stable workspace-relative hint when under .agents
        path_hint = path_out
        for marker in (".agents/skills", "bundled_skills"):
            idx = path_out.replace("\\", "/").lower().find(marker)
            if idx >= 0:
                path_hint = path_out.replace("\\", "/")[idx:]
                break
        family = "agent-ops" if "agent-ops" in path_out.replace("\\", "/") else "agents"
        return {
            "name": name,
            "path": path_out,
            "path_hint": path_hint,
            "description": desc or content[:120].replace("\n", " "),
            "family": family,
            "source_root": str(source_root.resolve()),
        }
    except Exception:
        return None


def build_catalog(skills_dir: str | Path | Sequence[str | Path] | None = None) -> List[CatalogEntry]:
    """Index SKILL.md under one dir or many roots (dedupe by resolved path)."""
    if skills_dir is None:
        roots = resolve_skill_roots()
    elif isinstance(skills_dir, (str, Path)):
        roots = [Path(skills_dir)]
    else:
        roots = [Path(p) for p in skills_dir]

    catalog: List[CatalogEntry] = []
    seen_files: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for skill_md in root.rglob("SKILL.md"):
            key = str(skill_md.resolve())
            if key in seen_files:
                continue
            seen_files.add(key)
            entry = _index_skill_md(skill_md, root)
            if entry:
                catalog.append(entry)
    return catalog


def filter_catalog(
    catalog: CatalogInput, query: str, limit: int = 20
) -> List[CatalogEntry]:
    if isinstance(catalog, dict):
        entries = list(catalog.values())
    else:
        entries = catalog

    if not query:
        return entries[:limit]

    q_lower = query.lower()
    tokens = [t for t in q_lower.replace("/", " ").replace("-", " ").split() if t]
    matched = []

    for item in entries:
        name = item.get("name", "")
        desc = item.get("description", "")
        path = item.get("path", "")
        family = item.get("family", "")
        blob = f"{name} {desc} {path} {family}".lower()
        if q_lower in blob or any(t in blob for t in tokens):
            matched.append(item)

    return matched[:limit] if matched else entries[:limit]


def suggest_from_catalog(
    catalog: CatalogInput,
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
        "roots_note": "Catalog merges .agents/skills + agent-ops (bundled) + GODKILLER_SKILLS_ROOTS",
    }
