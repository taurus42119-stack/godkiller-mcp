<p align="center">
  <img src="docs/assets/godkiller-mcp-banner.png" alt="GODKILLER MCP" width="520" />
</p>

# GODKILLER MCP

MCP for Antigravity / Cursor / Claude Desktop.  
Plan → gate → verify on disk → `claim_done`. Chat does not count.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml)

[Instagram @Kayvin.th](https://instagram.com/Kayvin.th)

---

## Install

```bash
pip install godkiller-mcp
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

`python -m godkiller_mcp.server` works too.  
One `GODKILLER_HOME` per host. Do not share across concurrent sessions.

Ship posture: wire PreToolUse → `godkiller-write-guard`, then set `GODKILLER_WRITE_GUARD_PROVEN=1`.  
Native Write is not blocked until that hook is real. Details: [`docs/WRITE_GUARD_HOOKS.md`](docs/WRITE_GUARD_HOOKS.md) · [`docs/HOST_VS_MCP.md`](docs/HOST_VS_MCP.md) · [`docs/SEAL_KEY.md`](docs/SEAL_KEY.md).

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

## Limits

- Gates apply to GODKILLER tool calls. Not an OS lockdown. Not Enterprise SaaS.
- Native Write/Edit bypass MCP unless the host PreToolUse hook is proven.
- Not a claim that WITH beats Bare on every oracle.

[`SECURITY.md`](SECURITY.md)

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
