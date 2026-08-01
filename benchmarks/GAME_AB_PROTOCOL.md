# Game arena A/B — pointer

Canonical protocol lives on the Desktop arena:

`%USERPROFILE%\Desktop\GODKILLER_GAME_ARENA\GAME_AB_PROTOCOL.md`

Commands:

```powershell
$env:GODKILLER_GAME_ARENA_ROOT = "$env:USERPROFILE\Desktop\GODKILLER_GAME_ARENA"
python -m benchmarks.reset_game_arena
python -m benchmarks.score_game --arm 3_WITHOUT_MCP
python -m benchmarks.score_game --arm 2_WITH_MCP
python -m benchmarks.score_game --compare
```
