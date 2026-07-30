# ⚡ GODKILLER MCP SERVER (`godkiller-mcp`)

> Local quality-control toolkit and MCP server for LLM coding agents (active development)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-active--development-orange.svg)](https://github.com/taurus42119-stack/godkiller-mcp)

⭐ If this project helps your agent workflow, a GitHub Star is appreciated.

💬 Contact:
- Facebook: [Pronphorm Pakdee](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee)
- Instagram: [@Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Quick install

```bash
git clone https://github.com/taurus42119-stack/godkiller-mcp.git
cd godkiller-mcp
pip install -e ".[scrape]"
# or: pip install -e .
pytest -q
```

Register in `mcp_config.json`:

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "python",
      "args": ["-m", "godkiller_mcp.server"]
    }
  }
}
```

Optional: set `GODKILLER_TOOLS_DIR` if you keep local binaries (`rg`, `fd`, `snyk`, `ast-grep`) outside `PATH`.

---

## Security notes (honest)

- **Scope-safe `.env` loading:** `ScopeSafeSecretsLoader` keeps secrets in an in-memory dict and does **not** write them into `os.environ`. The server exposes `godkiller_secret_keys` (key names only; values never returned).
- **No telemetry:** this package does not phone home credentials.
- **Optional outbound network:** `godkiller_deep_scrape` can fetch public `http(s)` URLs when the agent calls it (localhost/link-local blocked). Do not treat the server as air-gapped if that tool is enabled.
- **Command execution:** verify/soak runners prefer `shell=False` via `safe_exec`. On Windows, shell may still be used as a last resort when a binary is missing.

---

## What it includes

| Area | Modules | Reality check |
| :--- | :--- | :--- |
| Intent routing | `epistemic_router` | Regex / slash-command classifier (`godkiller_route_intent`) |
| Policy / evidence | `policy`, `evidence_store`, `verify_bundle` | Task graph + local command verification |
| Code intel | `code_intel` | Python `ast` + regex CWE heuristics; optional external CLIs if on `PATH` |
| Loop guard | `loop_guard` | Detects repeated tool signatures |
| Marathon memory | `marathon`, `memory_lessons` | Local JSON / SQLite state |
| Vision | `vision_bridge` | Pillow size/format/variance checks (`godkiller_inspect_image`) |
| Browser bridge | `browser_bridge` | Evidence registration helper (not a full browser driver) |

Slash-oriented modes: `/ask`, `/plan`, `/debug`, `/ultradeep`, `/verify`.

---

## Tests

Minimal unit tests ship in `tests/`:

```bash
pytest -q
```

Larger sealed-arena / HumanEval-style numbers mentioned in older notes are **not reproduced in this public repository**. Treat them as experimental lab notes until artifact + CI are published here.

---

## License

MIT License © 2026 GODKILLER Team. See [LICENSE](LICENSE).
