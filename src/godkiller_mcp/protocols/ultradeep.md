---
name: ultradeep-protocol
description: Bundled fallback when project .agents/workflows/ultradeep.md is missing.
---

# Trigger Command: /ultradeep

Supreme Orchestrator + Marathon one-phase pacing + **per-file Think→Plan→Edit** (additive).

## World kernel
1. `activate_mode({mode:"ultradeep", goal, open_kernel_task:true, slug})`
2. `marathon_load_progress` / `marathon_init`
3. `marathon_search_gate` before first code write
4. ONE plan Phase per turn → `marathon_save_progress` → wake

## Per-file hard loop (additive — no batch rush)
For **every** file you will change inside the current Phase:
1. `ultradeep_queue_files(paths=[...])`
2. `ultradeep_think_file` — deep notes ≥120 chars + ≥3 hypotheses + tools used
3. `ultradeep_plan_file` — concrete edit plan for THAT file only
4. `check_edit_safe` / blast_radius for **that single path**
5. Edit only that file
6. Verify (tests / scan / screenshot as applicable)
7. `ultradeep_advance_file` → next file in queue

FORBIDDEN: editing many files in one rush without think+plan per file.

## Cursor agent 200% tool swarm
Use maximally: `gk_code`, `gk_scan`, `gk_browser`, `gk_evidence`, `gk_verify`, plus peer MCP
`jcodemunch`, `codebase-memory`, `chrome-devtools` when available. Parallel recon before writes.
