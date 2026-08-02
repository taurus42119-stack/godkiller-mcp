<p align="center">
  <img src="docs/assets/godkiller-mcp-banner.png" alt="GODKILLER MCP" width="520" />
</p>

# GODKILLER MCP

Agent IDEs skip steps, invent “done,” and rewrite files with no proof on disk.  
**GODKILLER** is the MCP that makes them earn it.

Plan → gate → verify on disk → `claim_done`.  
Chat is noise. The harness decides.

Built for **Google Antigravity**, also runs on Cursor / Claude Desktop.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml)

[Instagram @Kayvin.th](https://instagram.com/Kayvin.th)

---

## Why it exists

| Pain | What GODKILLER does |
| --- | --- |
| Agent jumps `/plan` → code → “finished” | Phase gates. Illegal skips get blocked. |
| “Tests passed” in chat only | Verify runs on disk. No digest, no claim. |
| Multi-file rush | `/ultradeep` — one file think → plan → edit. |
| Fake green / hollow stubs | Hollow + fault probe before `claim_done`. |
| Session amnesia | Task + evidence + memory under `.godkiller/`. |

**The flex:** the model can *propose* done. Only sealed evidence can *make* it done.

---

## What it is not

- Not an OS jail. Native Write/Edit still bypass until you wire PreToolUse → `godkiller-write-guard`.
- Not Enterprise / SSO / multi-tenant SaaS — local MCP, one process.
- Not a magic win over Bare agents on every short oracle puzzle.

Full stack: `PROFILE=ship` + workspace pin + seal + proven write-guard.  
[`docs/HOST_VS_MCP.md`](docs/HOST_VS_MCP.md) · [`docs/WRITE_GUARD_HOOKS.md`](docs/WRITE_GUARD_HOOKS.md) · [`docs/SEAL_KEY.md`](docs/SEAL_KEY.md)

---

## Install

```bash
pip install godkiller-mcp
# or: pip install "git+https://github.com/taurus42119-stack/godkiller-mcp.git"
```

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp",
      "env": {
        "GODKILLER_PROFILE": "ship",
        "GODKILLER_WORKSPACE": "/absolute/path/to/your/project",
        "GODKILLER_HOME": "/absolute/path/to/your/project/.godkiller-session",
        "GODKILLER_SEAL_KEY": "REPLACE_WITH_64_HEX",
        "GODKILLER_SEAL_REQUIRE_ENV": "1"
      }
    }
  }
}
```

Alternate: `python -m godkiller_mcp.server`.  
One `GODKILLER_HOME` per host — don’t share across concurrent sessions.

Modes (`/ask` `/plan` `/debug` `/ultradeep` `/view` `/verify`) ship inside the package — no root `.agents/` folder required.

---

## Tools

| | |
| --- | --- |
| `gk_meta` | status · plan |
| `gk_route` | modes |
| `gk_task` | open · blast · edit_safe |
| `gk_phase` | assert · claim_done |
| `gk_evidence` | shots · visual_step · critic |
| `gk_verify` | bundle · hollow · probe · exit |
| `gk_memory` | lessons · marathon |
| `gk_code` | map · search · council · swarm |
| `gk_guard` | write allowlist for host hooks |
| `gk_scan` | heuristic scan |
| `gk_browser` | Playwright fallback (prefer chrome-devtools when present) |
| `gk_mode` | protocols · skills |
| `gk_handoff` | spec / feedback |

---

## Security

[`SECURITY.md`](SECURITY.md)

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
