# Arena scorecard — `2_WITH_MCP` vs `3_WITHOUT_MCP`

Isolated lab arms (same model / same sealed oracle):

| Arm | Folder | Meaning |
| --- | --- | --- |
| WITH | `2_WITH_MCP` | Antigravity + GODKILLER MCP |
| WITHOUT | `3_WITHOUT_MCP` | Antigravity bare (no MCP) |

## 11-dimension comparison

| Dimension | Bare (`3_WITHOUT_MCP`) | + GODKILLER (`2_WITH_MCP`) | Winner |
| --- | --- | --- | --- |
| 1. Pass rate (sealed pytest) | 516 / 516 (100%) | 516 / 516 (100%) | Tie |
| 2. Execution speed | ~0.36–0.37s | ~0.31–0.32s (~16% faster) | GODKILLER |
| 3. Token usage | ~35k–46k | ~50k–60k (more for certainty) | Bare (cheaper) |
| 4. Code quality diff | +59 −52 (minimal patch) | +73 −54 (defensive guards) | GODKILLER |
| 5. AST density | 2,840 nodes | 3,120 nodes (~+9.8%) | GODKILLER |
| 6. Anti-hallucination | Can claim done while bugs remain | Forces live pytest / evidence before claim | GODKILLER |
| 7. Exhaustive read | Partial / suspected files | Full-scope read gate | GODKILLER |
| 8. Council / multi-persona | One-shot | Coder / Hacker / Optimizer debate | GODKILLER |
| 9. Engineering rules | Ungoverned | AGENTS.md + phase protocol | GODKILLER |
| 10. Defensive design | Localized patch risk | Guard clauses / type boundaries | GODKILLER |
| 11. Durable memory | Short `.txt` notes | Marathon state + memory graph | GODKILLER |

**Reading this honestly:** both arms can clear the sealed suite; GODKILLER’s edge is **process quality** (no fake done, deeper read, defensive code, durable state). Cost is **more tokens**.

Companion gate snapshot: `5_dimension_audit_log.json`.
