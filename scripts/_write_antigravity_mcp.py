"""Rewrite Antigravity MCP + skills JSON without UTF-8 BOM.

Portable: uses PATH / sys.executable / env overrides — no machine-specific paths.
Env:
  GK_SEAL (required) — seal key
  GK_SKILLS (required) — semicolon-separated skill roots
  GODKILLER_WORKSPACE — optional workspace root (default: parent of this package)
  GODKILLER_AGENTS_MD / GODKILLER_AGENTS_ROOT — optional overrides
  JCODEMUNCH_MCP / CODEBASE_MEMORY_MCP — optional absolute commands
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

seal = os.environ["GK_SEAL"].strip()
skills = os.environ["GK_SKILLS"].strip()

PKG_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = Path(
    os.environ.get("GODKILLER_WORKSPACE", str(PKG_ROOT.parent))
).expanduser().resolve()
AGENTS_ROOT = Path(
    os.environ.get("GODKILLER_AGENTS_ROOT", str(WORKSPACE / ".agents"))
).expanduser().resolve()
AGENTS_MD = Path(
    os.environ.get("GODKILLER_AGENTS_MD", str(AGENTS_ROOT / "AGENTS.md"))
).expanduser().resolve()


def _cmd(env_key: str, *candidates: str) -> str:
    explicit = os.environ.get(env_key, "").strip()
    if explicit:
        return explicit
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return candidates[0]


jcodemunch = _cmd("JCODEMUNCH_MCP", "jcodemunch-mcp")
codebase_memory = _cmd("CODEBASE_MEMORY_MCP", "codebase-memory-mcp")

cfg = {
    "mcpServers": {
        "chrome-devtools": {
            "command": "npx",
            "args": ["-y", os.environ.get("CHROME_DEVTOOLS_MCP_SPEC", "chrome-devtools-mcp@0.6.0")],
        },
        "jcodemunch-mcp": {
            "command": jcodemunch,
            "args": [],
        },
        "codebase-memory-mcp": {
            "command": codebase_memory,
        },
        "godkiller": {
            "command": sys.executable,
            "args": ["-m", "godkiller_mcp.server"],
            "env": {
                "GODKILLER_PROFILE": "ship",
                "GODKILLER_SEAL_KEY": seal,
                "GODKILLER_SKILLS_ROOTS": skills,
                "GODKILLER_AGENTS_MD": str(AGENTS_MD),
                "GODKILLER_AGENTS_ROOT": str(AGENTS_ROOT),
                "GODKILLER_WRITE_GUARD_WIRED": os.environ.get(
                    "GODKILLER_WRITE_GUARD_WIRED", "1"
                ),
                **(
                    {"GODKILLER_HOME": os.environ["GODKILLER_HOME"]}
                    if os.environ.get("GODKILLER_HOME", "").strip()
                    else {}
                ),
            },
        },
    }
}

skill_entries = []
for p in (
    AGENTS_ROOT / "skills",
    AGENTS_ROOT / "skills" / "agent-ops",
    PKG_ROOT / ".agents" / "skills",
    PKG_ROOT / "src" / "godkiller_mcp" / "bundled_skills" / "agent-ops",
):
    if p.is_dir():
        skill_entries.append({"path": str(p)})
skills_json = {"entries": skill_entries}

home = Path.home()
paths = [
    home / ".gemini" / "config" / "mcp_config.json",
    home / ".gemini" / "antigravity" / "mcp_config.json",
    home / ".gemini" / "antigravity" / "mcp" / "mcp_config.json",
    home / ".gemini" / "antigravity-ide" / "mcp_config.json",
]
text = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
for p in paths:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print("wrote", p)

skills_path = home / ".gemini" / "config" / "skills.json"
skills_path.write_text(json.dumps(skills_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", skills_path)

# Drop write-guard hook artifacts + heartbeat marker for gk_meta.status
try:
    from godkiller_mcp.write_guard import mark_write_guard_wired
    import subprocess

    for target in ("godkiller", "cursor"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "godkiller_mcp.write_guard",
                "install",
                "--target",
                target,
                "--workspace",
                str(WORKSPACE),
                "--force",
            ],
            check=False,
        )
    mark_write_guard_wired(source="sync:_write_antigravity_mcp")
    print("write_guard hook artifacts + ~/.godkiller/write_guard_host.json")
except Exception as exc:
    print("write_guard install skipped:", exc)

from godkiller_mcp.honesty import _read_server_names, mcp_config_candidates
from godkiller_mcp.skill_catalog import build_catalog, resolve_skill_roots

os.environ.setdefault("GODKILLER_SEAL_KEY", seal)
os.environ["GODKILLER_SKILLS_ROOTS"] = skills

for p in mcp_config_candidates():
    info = _read_server_names(p)
    if info.get("exists"):
        print(info["path"], "->", info.get("servers"), "gk=", info.get("has_godkiller"))

cat = build_catalog(resolve_skill_roots())
print(
    "skills_indexed=",
    len(cat),
    "agent_ops=",
    sum(1 for e in cat if e.get("family") == "agent-ops"),
)

from godkiller_mcp.server import FACADE_ACTIONS

print("facades=", sorted(FACADE_ACTIONS.keys()))
print("ok")
