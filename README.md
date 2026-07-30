# GODKILLER MCP

**The Antigravity phase kernel** — force Google Antigravity to plan, gate phases, prove on disk, then claim done.  
Built because Antigravity is strong… and loves to skip the boring engineering steps.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-success.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-12%20facades-purple.svg)](#slim-tool-surface-12-facades)

```bash
pip install godkiller-mcp
```

⭐ Star the repo if this upgrades your Antigravity workflow.  
**Contact:** [Facebook — Pronphorm Pakdee](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee) · [Instagram @Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Why this exists

Google **Antigravity** often:

- skips `/plan` and jumps into code  
- edits many files in one rush  
- says “fixed” without pytest on disk  
- loses intent across long sessions  

Other MCPs help agents *read* or *browse*. GODKILLER’s product is **governance**: search → plan → phase gates → per-file think/plan/edit → verify → `claim_done`.

```text
goal → /ask|/plan|/debug|/ultradeep|/verify
    → evidence + 9-step plan (when required)
    → edit only if gates pass
    → verify_bundle on disk
    → claim_done (blocked if proof missing)
```

---

## Lab results — Antigravity bare vs + GODKILLER

### Method

| Control | Value |
| --- | --- |
| **Model** | **Gemini 3.6 Flash (HIGH)** — one model, both arms |
| **🥊 Bare** | Antigravity **without** MCP → `3_WITHOUT_MCP` |
| **👑 + GODKILLER** | Antigravity **with** MCP → `2_WITH_MCP` |
| **Oracle** | Sealed pytest in `hidden_oracle/` (blind while coding) |

**Only variable:** MCP on vs off. No model swap.

Evidence: [`11_dimension_scorecard.md`](benchmarks/arena_logs/11_dimension_scorecard.md) · [`5_dimension_audit_log.json`](benchmarks/arena_logs/5_dimension_audit_log.json)

### Hard gates (arena gauntlet)

| Gate | What agents faced |
| --- | --- |
| Tier 1 Easy ×50 | div-by-zero, None, bounds, float edges |
| Tier 2 Medium ×150 | state / race / rollback / schema drift |
| Tier 3 Hard ×300 | concurrency, graph, cache, AST-level bugs |
| Nightmare enterprise | ledger / inventory deadlock stress |
| Anthropic TAU-style SOTA | state-drift / rate-limit / lock scenarios |
| Blind oracle pytest | green on disk — text “done” does not count |

### Full 11-dimension scorecard

| # | Dimension | 🥊 Bare Antigravity | 👑 Antigravity + GODKILLER | Winner |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate (sealed pytest) | 516 / 516 (100%) | 516 / 516 (100%) | Tie |
| 2 | Execution speed | 0.36–0.37s | **0.31–0.32s** (~16.2% faster) | GODKILLER |
| 3 | Token usage | **~35k–46k** (cheaper) | ~50k–60k (pay for certainty) | Bare |
| 4 | Code upgrade lines | +59 −52 (minimal patch) | **+73 −54** (defensive guards) | GODKILLER |
| 5 | AST density | 2,840 nodes | **3,120 nodes** (~+9.8%) | GODKILLER |
| 6 | Anti-hallucination | Can summarize “pass” while bugs remain | **Forces live pytest until green** | GODKILLER |
| 7 | Exhaustive read | Skims suspected spots | **Full-scope read gate** | GODKILLER |
| 8 | Council debate | One-shot | **Coder / Hacker / Optimizer** | GODKILLER |
| 9 | Engineering rules | No control rules | **AGENTS.md + phase protocol** | GODKILLER |
| 10 | Defensive design | Local patch (regression risk) | **Guard clauses + type boundaries** | GODKILLER |
| 11 | Durable memory | Short `.txt` notes | **Marathon state + memory graph** | GODKILLER |

**Verdict:** pass-rate **tie** on the sealed suite. GODKILLER wins **how** the work is done (no fake done, denser/safer code, durable process). Tradeoff = **more tokens**.

```bash
pytest -q   # package unit tests
```

---

## What you get

| Layer | What it enforces |
| --- | --- |
| **Phase machine** | `assert_phase` / `claim_done` — illegal skips blocked |
| **Plan OS** | 9-step blueprint before fix-phase edits |
| **Edit safety** | blast radius + `check_edit_safe` |
| **/ultradeep` | one plan phase per turn **+** think → plan → edit **one file** |
| **Verify** | commands on disk — text-only “done” fails |
| **Memory graph** | task → phase → evidence → lesson |
| **Extras** | `gk_code` / `gk_scan` / `gk_browser` |

### `/ultradeep` per-file loop

1. `ultradeep_queue` → 2. `ultradeep_think` (≥3 hypotheses) → 3. `ultradeep_plan`  
4. `check_edit_safe` **one path** → edit → verify → 5. `ultradeep_advance`  

Opt out: `per_file_gate=false`.

---

## Install & MCP config

```bash
pip install godkiller-mcp
# optional: pip install 'godkiller-mcp[browser]' && playwright install chromium
# optional: pip install 'godkiller-mcp[scrape]'
```

```json
{
  "mcpServers": {
    "godkiller": { "command": "godkiller-mcp" }
  }
}
```

Or: `"command": "python", "args": ["-m", "godkiller_mcp.server"]`  
Optional: `GODKILLER_TOOLS_DIR` for `rg` / `semgrep` / etc.

From source: `git clone` → `pip install -e ".[all]"` → `pytest -q`

---

## Slim tool surface (12 facades)

| Tool | Role |
| --- | --- |
| `gk_route` | Intent → `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| `gk_mode` | Protocols, skills, ultradeep file gate |
| `gk_task` | open, hypothesize, blast_radius, edit_safe |
| `gk_phase` | assert, claim_done, rubric |
| `gk_evidence` | submit, capture_shot, visual_critic, journeys |
| `gk_verify` | pytest bundle, soak, loop_*, competitor, ladder |
| `gk_memory` | lessons, marathon, query_graph, what_blocked |
| `gk_code` | map, search, read_full, ast_grep, council, … |
| `gk_scan` | AST/CWE + optional Semgrep |
| `gk_browser` | Playwright navigate / snapshot / click / fill |
| `gk_handoff` | write_spec / write_feedback |
| `gk_meta` | plan_template / plan_validate |

---

## Modes

| Mode | Job |
| --- | --- |
| `/ask` | Explore — no app code edits |
| `/plan` | 9-step spec before build |
| `/debug` | Repro + hypothesis before fix |
| `/ultradeep` | Marathon + max tools + per-file gate |
| `/verify` | Proof, then claim_done |

---

## Security (short)

- Scope-safe secrets — MCP lists **key names only**, values stay local  
- Prefer `shell=False` for verify/soak  
- Scrape/browser are explicit tools, not silent phone-home  
- No machine-local paths committed to the public repo  

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
