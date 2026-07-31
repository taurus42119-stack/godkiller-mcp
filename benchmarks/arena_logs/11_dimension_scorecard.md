# Arena scorecard

Produced by:

```bash
python -m benchmarks.run_arena
python -m benchmarks.grade_arena
```

| Control | Value |
| --- | --- |
| Gauntlet | `benchmarks/gauntlet` |
| Runner | `benchmarks.run_arena` |
| Grader | `benchmarks.grade_arena` |

Latest graded run (engine gauntlet): see `graded_scorecard.json` / `arena_run.json`.

| Dimension | Value |
| --- | --- |
| Pass rate | 100% |
| Output integrity | 100 (full pytest body) |
| Overall | 100 |

Kernel arms (`2_WITH_MCP` / `3_WITHOUT_MCP`) remain the lab comparison when those trees are present; engine gauntlet is always reproducible from this repo.
