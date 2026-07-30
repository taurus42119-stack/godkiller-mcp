# GODKILLER MCP

**The Antigravity phase kernel** — an MCP built for Google Antigravity agents that skip planning, rush multi-file edits, and claim “done” without proof on disk.

Other tooling helps agents *read code* or *drive a browser*. GODKILLER makes the agent **obey an engineering process**: search → plan → phase gates → per-file think/plan/edit → verify → only then `claim_done`.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-success.svg)](tests/)

⭐ If this upgrades your Antigravity agent workflow, a GitHub star helps a lot.

**Contact:** [Facebook — Pronphorm Pakdee](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee) · [Instagram @Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Why this exists (the real pitch)

Google **Antigravity** is powerful — and often **refuses to split work into phases**. Typical failure modes:

- Jumps straight into code with no `/plan`
- Edits many files in one rush
- Says “fixed” without running tests on disk
- Loses intent across long sessions
- Skips web/search because local skills “already know enough”

**Almost nobody ships an MCP whose main product is fixing that.** GODKILLER was designed for that gap first. Code search, Semgrep, Playwright, and memory graph grew around the kernel — force multipliers, not the headline.

```text
User goal
  → /ask | /plan | /debug | /ultradeep | /verify
  → open task + evidence store
  → forced search / 9-step plan (when required)
  → edit only when gates pass
  → verify_bundle (pytest / commands) on disk
  → request_claim_done  (blocked if evidence missing)
```

---

## Lab results (our arena)

Same isolated sandbox: **Bare AI** vs **AI + GODKILLER**, scored on *our* governance rubric (phases / evidence / verify / taste gates) — not “this MCP invents perfect code for every problem on Earth.”

Evidence (2 files only):

- [`benchmarks/arena_logs/5_dimension_audit_log.json`](benchmarks/arena_logs/5_dimension_audit_log.json)
- [`benchmarks/arena_logs/real_200_benchmark_report.md`](benchmarks/arena_logs/real_200_benchmark_report.md)

### Snapshot — 5 dimensions (arena arms)

| Dimension | Bare AI | + GODKILLER |
| --- | ---: | ---: |
| Code correctness (arena pytest) | 0 | **100** |
| Reconnaissance / full-read gate | 20 | **100** |
| Security & hardening gate | 100 | **100** |
| Anti-hallucination / evidence gate | 0 | **100** |
| UI taste gate | 50 | **100** |
| **Rubric overall** | **34** | **100** |
| Pytest on disk | fail | **pass** |

`100` here means **the arm cleared that gate in this arena**, not a universal IQ score. Bare AI often fails gates that GODKILLER forces (evidence, verify, claim).

Broader sealed-task rollup (same thesis, more rows): see the report file linked above — same caveat applies.

### Package unit tests

```bash
pytest -q
```

---

## What you get

| Layer | What it enforces |
| --- | --- |
| **Phase machine** | `assert_phase` / `claim_done` — illegal skips blocked |
| **Plan OS** | 9-step blueprint validate before fix-phase edits |
| **Edit safety** | blast radius + `check_edit_safe` before mutation |
| **/ultradeep** | One plan phase per turn (marathon) **and** think → plan → edit **one file at a time** |
| **Verify** | Live commands on disk — text-only “done” is not enough |
| **Memory graph** | Task → phase → evidence → lesson |
| **Extras** | `gk_code` / `gk_scan` / `gk_browser` when you need depth |

### `/ultradeep` per-file loop (additive)

1. Queue files → `ultradeep_queue`  
2. Deep think (≥3 hypotheses) → `ultradeep_think`  
3. Per-file plan → `ultradeep_plan`  
4. `check_edit_safe` with **one path** → edit → verify  
5. `ultradeep_advance` → next file  

Opt out: `per_file_gate=false` on activate.

---

## Install

```bash
pip install godkiller-mcp
# optional:
#   pip install 'godkiller-mcp[browser]' && playwright install chromium
#   pip install 'godkiller-mcp[scrape]'
```

```bash
git clone https://github.com/taurus42119-stack/godkiller-mcp.git
cd godkiller-mcp
pip install -e ".[all]"
pytest -q
```

### MCP config (Antigravity / Cursor / Claude Desktop)

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp"
    }
  }
}
```

Or: `"command": "python", "args": ["-m", "godkiller_mcp.server"]`

Optional: `GODKILLER_TOOLS_DIR` for `rg` / `semgrep` / etc. not on `PATH`.

---

## Slim tool surface (12 facades)

| Tool | Role |
| --- | --- |
| `gk_route` | Classify intent → `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| `gk_mode` | Activate protocols, skills catalog, ultradeep file gate |
| `gk_task` | open, hypothesize, blast_radius, edit_safe, failing_slice |
| `gk_phase` | assert, claim_done, rubric |
| `gk_evidence` | submit, capture_shot, visual_critic, journeys |
| `gk_verify` | bundle (pytest), soak, loop_*, competitor, ladder |
| `gk_memory` | lessons, marathon, query_graph, what_blocked |
| `gk_code` | map, search, read_full, ast_grep, council, … |
| `gk_scan` | AST/CWE heuristics + optional Semgrep |
| `gk_browser` | Playwright navigate / snapshot / screenshot / click / fill |
| `gk_handoff` | write_spec / write_feedback gates |
| `gk_meta` | plan_template / plan_validate (9-step) |

---

## Modes

| Mode | Job |
| --- | --- |
| `/ask` | Explore — no application code edits |
| `/plan` | Spec + research — 9-step plan before build |
| `/debug` | Reproduce + hypothesize before fix |
| `/ultradeep` | Marathon + max tool swarm + per-file gate |
| `/verify` | Empirical proof, then claim_done |

Protocols load from `.agents/workflows/` when present; package ships a bundled `/ultradeep` fallback.

---

## Security (short)

- Secrets via scope-safe loader — key names only over MCP, values stay local  
- Verify/soak prefer safer process exec (`shell=False` where possible)  
- Optional scrape/browser are explicit tools, not silent phone-home  

---

## License

MIT © 2026 GODKILLER Team — see [LICENSE](LICENSE)
