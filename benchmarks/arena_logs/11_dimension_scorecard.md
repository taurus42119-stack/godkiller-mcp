# Arena — `2_WITH_MCP` vs `3_WITHOUT_MCP`

| Control | Value |
| --- | --- |
| Runtime | Gemini 3.6 Flash (HIGH) |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | `hidden_oracle/` |

Variable: MCP off / on.

## Gauntlet

| Gate | Load |
| --- | --- |
| Tier 1 | ×50 |
| Tier 2 | ×150 |
| Tier 3 | ×300 |
| Nightmare | enterprise |
| TAU-style SOTA | state / rate / lock |
| Blind oracle | disk green |

## Scorecard (11)

| # | Dimension | Bare | GODKILLER | Winner |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate | 516 / 516 | 516 / 516 | Tie |
| 2 | Speed | 0.36–0.37s | 0.31–0.32s (−16.2%) | GODKILLER |
| 3 | Tokens | ~35k–46k | ~50k–60k | Bare |
| 4 | Diff mass | +59 −52 | +73 −54 | GODKILLER |
| 5 | AST nodes | 2,840 | 3,120 (+9.8%) | GODKILLER |
| 6 | Anti-fake-claim | summary w/o green | live pytest gate | GODKILLER |
| 7 | Read scope | partial | full-scope gate | GODKILLER |
| 8 | Council | none | Coder / Hacker / Optimizer | GODKILLER |
| 9 | Rules | none | AGENTS.md + phases | GODKILLER |
| 10 | Defense | local patch | guards + type bounds | GODKILLER |
| 11 | Memory | `.txt` | marathon + graph | GODKILLER |

Companion: `5_dimension_audit_log.json`.
