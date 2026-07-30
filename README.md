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

Antigravity skips phases. GODKILLER does not allow that.

| Failure mode | Kernel response |
| --- | --- |
| No `/plan` | plan / phase gates |
| Multi-file rush | `/ultradeep` one-file think → plan → edit |
| Fake “done” | `verify_bundle` + `claim_done` block |
| Session amnesia | marathon + memory graph |

```text
goal → mode → evidence/plan → gated edit → disk verify → claim_done
```

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

### Gauntlet

| Gate | Load |
| --- | --- |
| Tier 1 | ×50 |
| Tier 2 | ×150 |
| Tier 3 | ×300 |
| Nightmare | enterprise deadlock / ledger stress |
| TAU-style SOTA | state-drift / rate-limit / locks |
| Blind oracle | disk green required |

### Scorecard (11)

| # | Dimension | Bare | GODKILLER | Winner |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate | 516 / 516 | 516 / 516 | Tie |
| 2 | Speed | 0.36–0.37s | **0.31–0.32s** (−16.2%) | GODKILLER |
| 3 | Tokens | **~35k–46k** | ~50k–60k | Bare |
| 4 | Diff mass | +59 −52 | **+73 −54** | GODKILLER |
| 5 | AST nodes | 2,840 | **3,120** (+9.8%) | GODKILLER |
| 6 | Anti-fake-claim | summary without green | **live pytest gate** | GODKILLER |
| 7 | Read scope | partial skim | **full-scope gate** | GODKILLER |
| 8 | Council | none | **Coder / Hacker / Optimizer** | GODKILLER |
| 9 | Rules | none | **AGENTS.md + phases** | GODKILLER |
| 10 | Defense | local patch | **guards + type bounds** | GODKILLER |
| 11 | Memory | `.txt` | **marathon + graph** | GODKILLER |

Pass-rate tie. Process dominance: GODKILLER. Token premium: accepted.

---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | `assert_phase` / `claim_done` |
| Plan OS | 9-step validate before fix edits |
| Edit safety | blast radius + `check_edit_safe` |
| `/ultradeep` | one phase/turn · one file/edit cycle |
| Verify | disk commands only |
| Memory | task → phase → evidence → lesson |
| Surface | `gk_code` / `gk_scan` / `gk_browser` |

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
Optional: `GODKILLER_TOOLS_DIR`

---

## Facades (12)

| Tool | Domain |
| --- | --- |
| `gk_route` | `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| `gk_mode` | protocol · skills · file gate |
| `gk_task` | open · blast · edit_safe |
| `gk_phase` | assert · claim_done · rubric |
| `gk_evidence` | submit · shot · critic · journey |
| `gk_verify` | bundle · soak · loop · competitor |
| `gk_memory` | lessons · marathon · graph |
| `gk_code` | map · search · read_full · council |
| `gk_scan` | AST/CWE · Semgrep |
| `gk_browser` | navigate · snapshot · click · fill |
| `gk_handoff` | spec · feedback |
| `gk_meta` | plan_template · plan_validate |

---

## Modes

| Mode | Contract |
| --- | --- |
| `/ask` | no application edits |
| `/plan` | 9-step before build |
| `/debug` | repro + hypothesis before fix |
| `/ultradeep` | marathon · max tools · per-file gate |
| `/verify` | proof → claim_done |

---

## Security

- Secret values never returned over MCP (names only)  
- Prefer `shell=False` verify/soak  
- Network scrape/browser are explicit invocations  

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
