# Arena — `2_WITH_MCP` vs `3_WITHOUT_MCP`

| Control | Value |
| --- | --- |
| Runtime | Gemini 3.6 Flash (HIGH) |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | `hidden_oracle/` |

Variable: MCP off / on.

## Scorecard (honest)

| # | Dimension | Bare | GODKILLER | Note |
| ---: | --- | --- | --- | --- |
| 1 | Pass rate | 516 / 516 | 516 / 516 | Tie |
| 2 | Speed | 0.36–0.37s | 0.31–0.32s | Process varies |
| 3 | Tokens | ~35k–46k | ~50k–60k | Kernel premium |
| 4 | Anti-fake-claim | summary w/o green | server `verify_bundle` | Kernel |

Retired as “wins”: Council / diff mass / AST node count / marketing gauntlet labels.
Those are not proof of kernel correctness.

Companion: `5_dimension_audit_log.json`.
