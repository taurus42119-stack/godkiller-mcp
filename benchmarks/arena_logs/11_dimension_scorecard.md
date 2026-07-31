# Arena scorecard

Honest A/B is pending a live Antigravity run (reset → bare → MCP → `score_11`).

Do **not** treat twin pre-solved 516/516 trees as a win.

```powershell
$env:GODKILLER_ARENA_ROOT="C:\Users\ASUS\Desktop\GODKILLER_ISOLATED_ARENA"
python -m benchmarks.reset_arena
# … Antigravity bare, then WITH MCP …
python -m benchmarks.score_11 --compare
```

Protocol: [`../ANTIGRAVITY_AB_PROTOCOL.md`](../ANTIGRAVITY_AB_PROTOCOL.md)

## Engine package suite (in-repo)

| Metric | Value |
| --- | --- |
| Collected | 346 |
| Passed | 346 / 346 |
