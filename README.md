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

### What is guaranteed vs experimental

| Tier | Meaning | Examples |
| --- | --- | --- |
| **Kernel** | Enforced in-process; adversarial tests cover forge/skip | phase machine, `verify_bundle` allowlist, server-only evidence, `claim_done` |
| **Supported** | Useful helpers; not proof of done | repo map, search, browser (optional extra) |
| **Experimental** | Heuristics / dry-run — do not treat as multi-agent or Snyk-class | static review checklist, regex autofix, pipeline dry-run |

State is stored under `GODKILLER_HOME` or `<cwd>/.godkiller/` — never under the installed package tree.

---

## Arena — Bare vs GODKILLER

| Control | Value |
| --- | --- |
| Runtime | Gemini 3.6 Flash (HIGH) — identical both arms |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | sealed `hidden_oracle/` pytest |

Single variable: MCP off / on.

Artifacts: [`11_dimension_scorecard.md`](benchmarks/arena_logs/11_dimension_scorecard.md) · [`5_dimension_audit_log.json`](benchmarks/arena_logs/5_dimension_audit_log.json)

### Scorecard (honest)

| # | Dimension | Bare | GODKILLER | Note |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate | 516 / 516 | 516 / 516 | Tie on oracle correctness |
| 2 | Speed | 0.36–0.37s | 0.31–0.32s | Process overhead varies |
| 3 | Tokens | ~35k–46k | ~50k–60k | Kernel costs tokens |
| 4 | Anti-fake-claim | summary without green | live pytest via `verify_bundle` | Kernel claim |

Older tables that ranked “Council / diff mass / AST nodes” as wins are retired — those are not enterprise proof.

---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | `assert_phase` / `claim_done` (illegal jumps error) |
| Plan OS | 9-step validate before fix edits |
| Edit safety | workspace path check + blast radius |
| `/ultradeep` | one phase/turn · one file/edit cycle |
| Verify | allowlisted disk commands only; server-authored evidence |
| Memory | task → phase → evidence → lesson |

### `/ultradeep`

`queue` → `think` (≥3 hypotheses) → `plan` → `edit_safe` (1 path) → verify → `advance`

---

## Install

```bash
pip install godkiller-mcp
# pip install 'godkiller-mcp[browser]' && playwright install chromium
# pip install 'godkiller-mcp[scrape]'
```

```json
{
  "mcpServers": {
    "godkiller": { "command": "godkiller-mcp" }
  }
}
```

Alternate: `python -m godkiller_mcp.server`  
Optional: `GODKILLER_HOME`, `GODKILLER_TOOLS_DIR`  
Dev-only soft gates: `GODKILLER_DEV_RELAX=1`

---

## Facades (12)

| Tool | Domain | Tier |
| --- | --- | --- |
| `gk_route` | `/ask` `/plan` `/debug` `/ultradeep` `/verify` | Supported |
| `gk_mode` | protocol · skills · file gate | Kernel / Supported |
| `gk_task` | open · blast · edit_safe | Kernel |
| `gk_phase` | assert · claim_done · rubric | Kernel |
| `gk_evidence` | submit · shot · critic · journey | Kernel (typed) |
| `gk_verify` | bundle · soak · loop · competitor | Kernel / Supported |
| `gk_memory` | lessons · marathon · graph | Supported |
| `gk_code` | map · search · read_full · checklist | Supported / Experimental |
| `gk_scan` | regex CWE heuristics · Semgrep optional | Experimental / Supported |
| `gk_browser` | navigate · snapshot · click · fill | Supported |
| `gk_handoff` | spec · feedback | Supported |
| `gk_meta` | plan_template · plan_validate | Kernel |

---

## Modes

| Mode | Contract |
| --- | --- |
| `/ask` | no application edits |
| `/plan` | 9-step before build |
| `/debug` | repro + hypothesis before fix |
| `/ultradeep` | marathon · per-file gate |
| `/verify` | proof → claim_done |

---

## Security

- Secret values never returned over MCP (names only)  
- Prefer `shell=False` verify/soak  
- Verify commands are allowlisted (pytest / unittest / ruff / mypy)  
- Network scrape/browser are explicit invocations  
- `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE` cannot be forged via `submit_evidence`

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
