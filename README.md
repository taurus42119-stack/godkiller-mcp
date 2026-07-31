# GODKILLER MCP

Phase kernel for **Google Antigravity**.  
Plan. Gate. Prove on disk. Then claim done — or get blocked.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-success.svg)](tests/)

```bash
pip install godkiller-mcp
```

**Contact:** [Facebook](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee) · [Instagram @Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Mission

Antigravity skips phases. GODKILLER blocks that when the kernel path is used.

| Failure mode | Kernel response |
| --- | --- |
| No `/plan` | plan / phase gates |
| Multi-file rush | `/ultradeep` one-file think → plan → edit |
| Fake “done” | server-authored `verify_bundle` + `claim_done` block |
| Session amnesia | marathon + memory graph |

```text
goal → mode → evidence/plan → gated edit → disk verify → claim_done
```

### What is guaranteed vs helpers

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Kernel** | Enforced; forge/skip covered by tests | phase, server-only evidence, verify allowlist, claim_done |
| **Supported** | Real implementations, not proof of done | exhaustive full-file read, AST council, pipeline executor, vision+elements |
| **Optional** | Needs extra install | Playwright browser, pytesseract OCR |

State: `GODKILLER_HOME` or `<cwd>/.godkiller/` — never under site-packages.

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

---

## Reproducible gauntlet (not vibes)

Legacy hand-written “516 / 0.38s” scorecards are **retired** as marketing.  
Run a real suite and write JSON with full pytest output:

```bash
python -m benchmarks.run_arena
# writes benchmarks/arena_logs/arena_run.json
pytest -q tests benchmarks/gauntlet
```

Artifacts: [`arena_run.json`](benchmarks/arena_logs/arena_run.json) (generated) · historical notes in [`arena_logs/`](benchmarks/arena_logs/)

---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | illegal jumps error |
| Plan OS | 9-step validate before fix edits |
| Edit safety | workspace path check + blast radius |
| `/ultradeep` | one file/edit cycle |
| Verify | allowlisted disk commands; server-authored evidence |
| Vision | blank/size + `expected_elements` via OCR or sidecar `.txt` |
| Council | multi-pass AST (structure / security / complexity) |
| Pipeline | topological execute via real tool handlers |
| Read | full file contents by default (truncate only if requested) |

### `/ultradeep`

`queue` → `think` (≥3 hypotheses) → `plan` → `edit_safe` (1 path) → verify → `advance`

---

## Install

```bash
pip install godkiller-mcp
# pip install 'godkiller-mcp[browser]' && playwright install chromium
# pip install 'godkiller-mcp[scrape]'
# optional OCR: pip install pytesseract  (+ Tesseract binary)
```

```json
{
  "mcpServers": {
    "godkiller": { "command": "godkiller-mcp" }
  }
}
```

Alternate: `python -m godkiller_mcp.server`  
Env: `GODKILLER_HOME`, `GODKILLER_TOOLS_DIR`, `GODKILLER_DEV_RELAX=1` (dev only)

---

## Facades (12)

| Tool | Domain |
| --- | --- |
| `gk_route` | `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| `gk_mode` | protocol · skills · file gate |
| `gk_task` | open · blast · edit_safe |
| `gk_phase` | assert · claim_done · rubric |
| `gk_evidence` | submit · shot · critic · journey · inspect_image |
| `gk_verify` | bundle · soak · loop · competitor |
| `gk_memory` | lessons · marathon · graph |
| `gk_code` | map · search · read · council · pipeline · self_heal |
| `gk_scan` | regex CWE · Semgrep optional |
| `gk_browser` | Playwright navigate/snapshot/click/fill |
| `gk_handoff` | spec · feedback |
| `gk_meta` | plan_template · plan_validate |

---

## Security

- Secret values never returned over MCP (names only)  
- Verify allowlist: pytest / unittest / ruff / mypy  
- `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE` cannot be forged via `submit_evidence`  
- Network scrape/browser are explicit invocations  

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
