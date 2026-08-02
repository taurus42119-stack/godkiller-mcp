<p align="center">
  <img src="docs/assets/godkiller-mcp-banner.png" alt="GODKILLER MCP" width="520" />
</p>

# GODKILLER MCP

**Gates on disk beat chat.**  
The agent may *say* done. The harness decides.

MCP for **Google Antigravity** (also Cursor / Claude Desktop).  
Plan → gate → verify on disk → `claim_done`.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml)

[Instagram @Kayvin.th](https://instagram.com/Kayvin.th)

---

## Who it’s for

Developers, AI engineers, and power users who run **coding agents** hard — and are tired of trusting the chat bubble.

| Pain | What usually happens | What GODKILLER does |
| --- | --- | --- |
| **Fake completion** | “Fixed!” in chat — tests fail, stubs ship | No `claim_done` without disk verify + evidence |
| **Token bloat** | Fat JSON / schema dumps flood context | Compact payloads by default |
| **Skipped ritual** | Jumps plan → edit → “done” | Phase gates · `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| **Unproven edits** | Files change with no blast / proof | `edit_safe` · blast · hollow · fault probe |

---

## Why it hits

**Proof over promises.** Chat vibes don’t move the gate. Sealed evidence on disk does.

**Phase kernel.** `gk_route` puts the agent on a real pipeline — not free-form hope.

**One MCP surface.** Code · scan · browser · guard · handoff · memory — facades in one place, judge for the rest.

**The flex:** the model proposes. GODKILLER disposes.

```text
goal → mode → plan → search/blast → gated edit
    → disk verify → hollow → probe → exit → claim_done | blocked
```

---

## What it is not

- Not an OS lockdown. Native Write/Edit still bypass until PreToolUse → `godkiller-write-guard` is proven.
- Not Enterprise / SSO / multi-tenant SaaS — local single-process MCP.
- Not a guarantee that WITH beats Bare on every short oracle puzzle.

Ship posture: `PROFILE=ship` + workspace pin + seal + proven write-guard.  
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
One `GODKILLER_HOME` per host. Modes ship inside the package — no root `.agents/` required.

---

## Tools

| | |
| --- | --- |
| `gk_meta` | status · plan |
| `gk_route` | `/ask` `/plan` `/debug` `/ultradeep` `/view` `/verify` |
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
