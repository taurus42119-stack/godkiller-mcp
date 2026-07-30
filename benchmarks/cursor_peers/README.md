# Cursor peer MCP comparison harness (manual + scripted checklist)

Peers configured in `%USERPROFILE%\.cursor\mcp.json`:
- jcodemunch — code intel
- codebase-memory-mcp — codebase graph memory
- chrome-devtools — real browser
- godkiller-mcp — phase / evidence / verify orchestrator

## Protocol

Run the **same** Antigravity bugfix task three times (fresh chat each arm):

| Arm | MCP enabled | Others disabled |
| --- | --- | --- |
| 1 | jcodemunch only | yes |
| 2 | codebase-memory-mcp only | yes |
| 3 | godkiller only | yes |

Score each arm 0/1 for:

1. `phase_split` — agent advanced through explicit phases before editing
2. `plan_first` — written plan/spec before mutation
3. `disk_verify` — ran pytest or verify commands on disk
4. `no_false_claim` — did not claim done without green tests
5. `ui_proof` — if UI task, captured screenshot/journey evidence

## Record sheet

Fill after runs and commit updates here.

| Metric | jcodemunch | codebase-memory | godkiller |
| --- | ---: | ---: | ---: |
| phase_split |  |  |  |
| plan_first |  |  |  |
| disk_verify |  |  |  |
| no_false_claim |  |  |  |
| ui_proof |  |  |  |
| **total / 5** |  |  |  |

## Expected GODKILLER edge

GODKILLER should win `phase_split`, `plan_first`, `disk_verify`, `no_false_claim` because `gk_phase` / `gk_meta.plan_validate` / `gk_verify.bundle` / claim gates encode those rules. jcodemunch should remain strong at raw code navigation; codebase-memory at source graph recall — different jobs.
