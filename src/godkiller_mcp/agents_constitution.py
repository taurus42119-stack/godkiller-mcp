"""Resolve and advertise the paired `.agents` constitution (AGENTS.md).

MCP + .agents ship together: status always tells the agent to read the
constitution path before claiming work is done.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.runtime_paths import package_root


def _candidates() -> List[Path]:
    out: List[Path] = []
    env_file = os.environ.get("GODKILLER_AGENTS_MD", "").strip()
    if env_file:
        out.append(Path(env_file).expanduser())
    env_root = os.environ.get("GODKILLER_AGENTS_ROOT", "").strip()
    if env_root:
        out.append(Path(env_root).expanduser() / "AGENTS.md")
        out.append(Path(env_root).expanduser() / ".agents" / "AGENTS.md")

    cwd = Path.cwd()
    out.append(cwd / ".agents" / "AGENTS.md")
    out.append(cwd / "AGENTS.md")
    parent = cwd.parent
    for _ in range(5):
        out.append(parent / ".agents" / "AGENTS.md")
        if parent.parent == parent:
            break
        parent = parent.parent

    pkg = package_root()
    out.append(pkg / ".agents" / "AGENTS.md")
    out.append(Path(__file__).resolve().parent / "bundled_agents" / "AGENTS.md")
    return out


def resolve_agents_md() -> Optional[Path]:
    for p in _candidates():
        try:
            if p.is_file():
                return p.resolve()
        except OSError:
            continue
    return None


def resolve_agents_root(agents_md: Optional[Path] = None) -> Optional[Path]:
    md = agents_md or resolve_agents_md()
    if md is None:
        return None
    # .../.agents/AGENTS.md → .agents ; else parent of file
    if md.parent.name == ".agents":
        return md.parent
    if (md.parent / "skills").is_dir():
        return md.parent
    return md.parent


def constitution_status() -> Dict[str, Any]:
    """Payload embedded in gk_meta.status — must_read is always true when file exists."""
    md = resolve_agents_md()
    root = resolve_agents_root(md)
    rules_preview: List[str] = []
    visual_qa = False
    if md and md.is_file():
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
            visual_qa = any(
                marker in text
                for marker in (
                    "Mandatory Visual QA Gate",
                    "Visual Screenshot Proof",
                    "UI visual",
                    "visual_step",
                    "Rule 8",
                )
            )
            for line in text.splitlines():
                s = line.strip()
                if s.startswith(("1. **", "2. **", "3. **", "4. **", "5. **", "6. **", "7. **", "8. **")):
                    rules_preview.append(s[:160])
                if len(rules_preview) >= 8:
                    break
        except OSError:
            text = ""
    exists = bool(md and md.is_file())
    return {
        "must_read_agents_md": True,
        "agents_md_path": str(md) if md else None,
        "agents_root": str(root) if root else None,
        "exists": exists,
        "supreme_law_preview": rules_preview,
        "has_visual_qa_rule_8": visual_qa,
        "order": (
            "BEFORE substantive edits or claim_done: open and follow agents_md_path "
            "(Supreme Law including Forced Search + Mandatory Visual QA Gate for UI/Web/3D). "
            "Call gk_mode.skill_catalog for skills under agents_root/skills. "
            ".agents + GODKILLER MCP are a paired pack — do not skip the constitution."
        ),
        "note": (
            "Soft host text without PreToolUse is still bypassable via native Write; "
            "WITH protocol and claim_done gates still require kernel evidence."
        ),
    }
