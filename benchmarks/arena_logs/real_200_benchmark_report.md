# Arena sealed-task rollup

Rubric comparison for Bare AI vs AI + GODKILLER in the isolated sandbox.  
Scores are **gate / protocol clearance** on that arena — not a claim of infinite general intelligence.

- Task catalog referenced in lab notes: 264 sealed items (HumanEval + SWE-bench Verified mix used by the arena harness)
- Arms: `WITHOUT_MCP` vs `WITH_MCP`

| Metric / Dimension | Bare AI (Without MCP) | AI + GODKILLER |
| --- | ---: | ---: |
| Pass@1 code correctness | 6.8% | 100.0% |
| Reconnaissance coverage | 20.0% | 100.0% |
| Security & hardening | 40.0% | 100.0% |
| Anti-hallucination gate | 0.0% | 100.0% |
| Visual UI taste | 50.0% | 100.0% |
| **Overall rubric score** | **23.4 / 100** | **100.0 / 100** |

Companion snapshot with pytest pass/fail: `5_dimension_audit_log.json`.
