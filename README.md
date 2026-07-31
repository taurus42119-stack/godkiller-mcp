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
| Fake “done” | `verify_bundle` + `claim_done` block (server-authored evidence only) |
| Session amnesia | marathon + memory graph |
| Weak review | LLM council — Coder / Hacker / Optimizer, multi-round debate |

```text
goal → mode → evidence/plan → gated edit → disk verify → claim_done
```

---

## Arena — Antigravity A/B (the real proof)

Pre-solved twins that both pass 516 prove nothing. The honest protocol:

1. Reset arms to sealed buggy `1_ORIGINAL`
2. You open **Antigravity** on `3_WITHOUT_MCP` with MCP **off** → agent tries → we score
3. Reset / open `2_WITH_MCP` with MCP **on** → agent tries → we score
4. Compare **11 dimensions** (fail-closed on missing evidence)

| Control | Value |
| --- | --- |
| Arena root | `GODKILLER_ISOLATED_ARENA` / `GODKILLER_ARENA_ROOT` |
| Baseline | `1_ORIGINAL` (never edit mid-run) |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | sealed `hidden_oracle/` |
| Protocol | [`benchmarks/ANTIGRAVITY_AB_PROTOCOL.md`](benchmarks/ANTIGRAVITY_AB_PROTOCOL.md) |

### 11 dimensions

| # | Dimension |
| ---: | --- |
| 1 | Code correctness (oracle pass %) |
| 2 | Oracle volume (≥516 collected) |
| 3 | Output integrity (full pytest body) |
| 4 | Delta from baseline (files actually changed) |
| 5 | Reconnaissance / exhaustive read artifacts |
| 6 | Phase discipline (task / plan / marathon) |
| 7 | Blast radius + edit-safe |
| 8 | Verify bundle + claim_done |
| 9 | Council (Coder / Hacker / Optimizer) |
| 10 | Security hardening signals |
| 11 | UI visual gate (critic / screenshots) |

```powershell
$env:GODKILLER_ARENA_ROOT="C:\Users\ASUS\Desktop\GODKILLER_ISOLATED_ARENA"
python -m benchmarks.reset_arena
# → open Antigravity bare, then:
python -m benchmarks.score_11 --arm 3_WITHOUT_MCP
# → open Antigravity + MCP, then:
python -m benchmarks.score_11 --arm 2_WITH_MCP
python -m benchmarks.score_11 --compare
```

Scorecard lands in `GODKILLER_ISOLATED_ARENA\logs\11_dimension_scorecard.md` after *your* runs — not a fake pre-fill.

### Engine gauntlet (in-package kernel proof)

| Gate | Load |
| --- | --- |
| Kernel forge/skip | adversarial + volume matrix |
| Phase illegal jumps | full forward-skip matrix |
| Verify allowlist | allow + deny command grids |
| Council host tally | all 8 vote combinations |
| Exhaustive read | 120 size variants (incl. >3000 chars) |
| Closed-task immutability | 80 variants |
| Package suite | **331** passed (`pytest -q`) |

```bash
python -m benchmarks.run_arena --mode engine
pytest -q
```

---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | `assert_phase` / `claim_done` |
| Plan OS | 9-step validate before fix edits |
| Edit safety | blast radius + path-safe `check_edit_safe` |
| `/ultradeep` | one phase/turn · one file/edit cycle |
| Verify | disk commands · `result_digest` · **fault_probe** kills weak suites |
| Hollow surface | unfinished bodies blocked before `claim_done` |
| Plan lock | write-through-plan — 9-step validate before edit/claim |
| Session ledger | hash chain under `.godkiller/session_ledger.jsonl` |
| Strict mode | `GODKILLER_STRICT=1` — privileged tools need `task_id` |
| Council | host debate (default) · optional API |
| Visual critic | **pixels required** — regex alone cannot GREEN |
| Recovery | self_heal = traceback parse → one fallback tool run |

```text
goal → mode → evidence/plan → gated edit → disk verify → hollow → claim_done
```

### `/ultradeep`

`queue` → `think` (≥3 hypotheses) → `plan` → `edit_safe` (1 path) → verify → `advance`

### Council

**Host mode (default):** MCP ส่งบท Coder / Hacker / Optimizer ให้โมเดลใน IDE → `council_submit` → `council_finalize`  

**API mode (optional):** `GODKILLER_LLM_API_KEY` / `OPENAI_API_KEY` + `mode=api`

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
Optional: `GODKILLER_HOME` · `GODKILLER_TOOLS_DIR` · `GODKILLER_LLM_API_KEY`

---

## Tools — Kernel vs recovery vs experimental

**Kernel (the product):** `gk_route` · `gk_mode` · `gk_task` · `gk_phase` · `gk_evidence` · `gk_verify` (bundle / hollow / **probe** / ledger) · `gk_memory` · `gk_code` (map / search / read_full / council*) · `gk_meta` (plan)

**Recovery:** `gk_code.self_heal` · `gk_code.pipeline`

**Optional / experimental:** `gk_browser` · `gk_scan` · `gk_handoff` · scrape · skillify · confidence · auto_fix · soak / competitor

Env: `GODKILLER_PLAN_LOCK=1` (default) · `GODKILLER_FAULT_PROBE=1` (default) · `GODKILLER_STRICT=1` (opt-in) · `GODKILLER_DEV_RELAX=1` (local soft bypass only)

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
- Prefer `shell=False` verify/soak · verify command allowlist  
- Forge-proof evidence types: `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE`  
- Network scrape/browser are explicit invocations  

State lives under `GODKILLER_HOME` or `<cwd>/.godkiller/`.

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
