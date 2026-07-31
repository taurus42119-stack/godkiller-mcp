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

## Arena — Bare vs GODKILLER

| Control | Value |
| --- | --- |
| Runtime | Gemini 3.6 Flash (HIGH) — identical both arms |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | sealed `hidden_oracle/` pytest |
| Engine gauntlet | `benchmarks/gauntlet` + `python -m benchmarks.run_arena` + `grade_arena` |

Single variable: MCP off / on.

### Gauntlet

| Gate | Load |
| --- | --- |
| Kernel forge/skip | adversarial + volume matrix |
| Phase illegal jumps | full forward-skip matrix |
| Verify allowlist | allow + deny command grids |
| Council host tally | all 8 vote combinations |
| Exhaustive read | 50 size variants (incl. >3000 chars) |
| Blind oracle | disk green + output integrity |

### Scorecard (reproducible)

| # | Dimension | Result |
| ---: | --- | --- |
| 1 | Collected | **211** |
| 2 | Passed | **211 / 211** |
| 3 | Wall clock | ~1.8s (runner) |
| 4 | Output integrity | **100** (full pytest body, not header-only) |
| 5 | Overall grade | **100** |
| 6 | Suspicious flags | **none** |

```bash
python -m benchmarks.run_arena
python -m benchmarks.grade_arena
# → arena_run.json + graded_scorecard.json
pytest -q
```

Artifacts: [`arena_run.json`](benchmarks/arena_logs/arena_run.json) · [`graded_scorecard.json`](benchmarks/arena_logs/graded_scorecard.json)
---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | `assert_phase` / `claim_done` |
| Plan OS | 9-step validate before fix edits |
| Edit safety | blast radius + path-safe `check_edit_safe` |
| `/ultradeep` | one phase/turn · one file/edit cycle |
| Verify | disk commands only · server-authored evidence |
| Council | host debate by default · optional API multi-round |
| Pipeline | topological tool execution |
| Memory | task → phase → evidence → lesson |
| Surface | `gk_code` / `gk_scan` / `gk_browser` |

### `/ultradeep`

`queue` → `think` (≥3 hypotheses) → `plan` → `edit_safe` (1 path) → verify → `advance`

### Council

**Host mode (default):** MCP ส่งบท Coder / Hacker / Optimizer ให้โมเดลใน IDE เล่นทีละมุม → `council_submit` → `council_finalize` รวมโหวต  

**API mode (optional):** ตั้ง `GODKILLER_LLM_API_KEY` หรือ `OPENAI_API_KEY` แล้วเรียก `mode=api` / `prefer_api=true` — เซิร์ฟเวอร์ดีเบตหลายรอบเอง  

ไม่มี key ก็ใช้ council ได้ (host) — API เป็นของเสริม ไม่ใช่ของบังคับ

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
| `gk_code` | map · search · read_full · council / council_submit / council_finalize · pipeline · self_heal |
| `gk_scan` | CWE heuristics · Semgrep |
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
- Prefer `shell=False` verify/soak · verify command allowlist  
- Forge-proof evidence types: `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE`  
- Network scrape/browser are explicit invocations  

State lives under `GODKILLER_HOME` or `<cwd>/.godkiller/`.

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
