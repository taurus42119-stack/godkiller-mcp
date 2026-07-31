# Antigravity A/B protocol (honest)

Goal: prove **Bare vs GODKILLER** with *your* Antigravity sessions — not pre-solved twins.

## Folders

| Path | Role |
| --- | --- |
| `1_ORIGINAL` | Sealed buggy baseline (never edit during a run) |
| `3_WITHOUT_MCP` | Bare arm — MCP **off** |
| `2_WITH_MCP` | GODKILLER arm — MCP **on** |
| `hidden_oracle/` | Sealed pytest (do not open / do not train on) |

## Steps

### 0) Reset both arms to the broken challenge

```powershell
cd "<path-to-godkiller_mcp_pypi_package>"
$env:GODKILLER_ARENA_ROOT="<your-arena-root>"
python -m benchmarks.reset_arena
```

### 1) Bare run (MCP off)

1. Open Antigravity on `...\GODKILLER_ISOLATED_ARENA\3_WITHOUT_MCP`
2. Confirm GODKILLER MCP is **disabled / removed**
3. Same model / same prompt budget as the WITH run
4. Ask the agent to fix the bugs so tests pass (do **not** paste oracle tests)
5. When the session ends, score:

```powershell
python -m benchmarks.score_11 --arm 3_WITHOUT_MCP
```

### 2) Reset WITH arm only (keep bare result on disk)

```powershell
python -m benchmarks.reset_arena --arm 2_WITH_MCP
```

(If you also polluted bare and need a clean WITH-only compare later, reset both and re-run bare first.)

### 3) GODKILLER run (MCP on)

1. Open Antigravity on `...\GODKILLER_ISOLATED_ARENA\2_WITH_MCP`
2. Enable `godkiller-mcp`
3. Same model / same prompt as bare
4. Prefer kernel path: plan → evidence → edit → verify → claim_done / council when relevant
5. Score:

```powershell
python -m benchmarks.score_11 --arm 2_WITH_MCP
```

### 4) Compare — 11 dimensions

```powershell
python -m benchmarks.score_11 --compare
```

Writes:

- `GODKILLER_ISOLATED_ARENA\logs\11_dimension_scorecard.json`
- `GODKILLER_ISOLATED_ARENA\logs\11_dimension_scorecard.md`

## 11 dimensions (fail-closed)

| # | Dimension | How scored |
| ---: | --- | --- |
| 1 | Code correctness | Oracle pass % |
| 2 | Oracle volume | Collected ≥ 516 |
| 3 | Output integrity | Full pytest body (not header-only) |
| 4 | Delta from baseline | Challenge files changed vs `1_ORIGINAL` |
| 5 | Reconnaissance | Exhaustive-read / full-content artifacts |
| 6 | Phase discipline | open_task / plan / marathon artifacts |
| 7 | Blast + edit-safe | Both tools evidenced |
| 8 | Verify + claim | verify_bundle + claim_done |
| 9 | Council | Coder/Hacker/Optimizer artifacts |
| 10 | Security hardening | Security / hacker / XSS signals in artifacts |
| 11 | UI visual gate | visual_critic and/or screenshots |

Missing evidence → **0**. Header-only pytest → **overall 0**.  
If an arm scores 516 with **zero** file delta from `1_ORIGINAL` → flagged as suspicious.

## Rules that keep it real

- Do not copy fixed files from one arm to the other.
- Do not edit `hidden_oracle/`.
- Do not hand-fix after the agent “finishes” unless you log it as human assist (then it is not a clean A/B).
- Same model + same time budget both arms.
- Kernel dims (5–11) score only from **this session**: `arm/.godkiller/`, `arm/session_evidence/`, `arm/arena/results/` — not old `.agents/plans` novels.
