# Arena scorecard — `2_WITH_MCP` vs `3_WITHOUT_MCP`

## Method

| Control | Value |
| --- | --- |
| Model | **Gemini 3.6 Flash (HIGH)** — one model for both arms |
| 🥊 Bare | `3_WITHOUT_MCP` — Antigravity, no MCP |
| 👑 + GODKILLER | `2_WITH_MCP` — Antigravity + GODKILLER MCP |
| Oracle | Sealed pytest in `hidden_oracle/` |

Only variable: MCP on vs off.

## Hard gates

| Gate | Arena source |
| --- | --- |
| Tier 1 Easy ×50 | `tier_1_easy_50.py` |
| Tier 2 Medium ×150 | `tier_2_medium_150.py` |
| Tier 3 Hard ×300 | `tier_3_hard_300.py` |
| Nightmare enterprise | `nightmare_app.py` |
| Anthropic TAU-style SOTA | `anthropic_sota.py` |
| Blind disk verify | `hidden_oracle/` pytest |

## Full 11-dimension comparison

| # | Dimension | 🥊 Bare Antigravity | 👑 + GODKILLER | Winner |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate | 516 / 516 (100%) | 516 / 516 (100%) | Tie |
| 2 | Execution speed | 0.36–0.37s | 0.31–0.32s (~16.2% faster) | GODKILLER |
| 3 | Token usage | ~35k–46k (cheaper) | ~50k–60k (certainty) | Bare |
| 4 | Code upgrade lines | +59 −52 minimal patch | +73 −54 defensive guards | GODKILLER |
| 5 | AST density | 2,840 nodes | 3,120 nodes (~+9.8%) | GODKILLER |
| 6 | Anti-hallucination | Can claim pass while bugs remain | Forces live pytest until green | GODKILLER |
| 7 | Exhaustive read | Skim suspected spots | Full-scope read gate | GODKILLER |
| 8 | Council debate | One-shot | Coder / Hacker / Optimizer | GODKILLER |
| 9 | Engineering rules | None | AGENTS.md + phase protocol | GODKILLER |
| 10 | Defensive design | Local patch / regression risk | Guard clauses + type boundaries | GODKILLER |
| 11 | Durable memory | Short `.txt` | Marathon state + memory graph | GODKILLER |

Companion: `5_dimension_audit_log.json`.
