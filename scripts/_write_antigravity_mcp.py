"""Rewrite Antigravity MCP + skills JSON without UTF-8 BOM."""
from __future__ import annotations

import json
import os
from pathlib import Path

seal = os.environ["GK_SEAL"].strip()
skills = os.environ["GK_SKILLS"].strip()

cfg = {
    "mcpServers": {
        "chrome-devtools": {
            "command": "npx",
            "args": ["-y", "chrome-devtools-mcp@latest"],
        },
        "jcodemunch-mcp": {
            "command": r"C:\Users\ASUS\AppData\Local\Programs\Python\Python312\Scripts\jcodemunch-mcp.exe",
            "args": [],
        },
        "codebase-memory-mcp": {
            "command": r"C:\Users\ASUS\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe",
        },
        "godkiller": {
            "command": r"C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe",
            "args": ["-m", "godkiller_mcp.server"],
            "env": {
                "GODKILLER_PROFILE": "ship",
                "GODKILLER_SEAL_KEY": seal,
                "GODKILLER_SKILLS_ROOTS": skills,
                "GODKILLER_AGENTS_MD": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\.agents\AGENTS.md",
                "GODKILLER_AGENTS_ROOT": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\.agents",
            },
        },
    }
}

skills_json = {
    "entries": [
        {"path": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\.agents\skills"},
        {"path": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\.agents\skills\agent-ops"},
        {
            "path": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\godkiller_mcp_pypi_package\.agents\skills"
        },
        {
            "path": r"C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\godkiller_mcp_pypi_package\src\godkiller_mcp\bundled_skills\agent-ops"
        },
    ]
}

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

# smoke: import server with seal set
from godkiller_mcp.server import FACADE_ACTIONS

print("facades=", sorted(FACADE_ACTIONS.keys()))
print("ok")
