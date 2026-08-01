---
name: ultradeep-protocol
description: Bundled fallback when project .agents/workflows/ultradeep.md is missing.
---

# Trigger Command: /ultradeep

Marathon one-phase pacing + **per-file Think→Plan→Edit** (additive). Hard gates stay on.

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

## Plan refute wake (HARD — before first edit)

After `gk_meta.plan_validate` succeeds:

1. `ultradeep_plan_refute` with ≥8 attacks on 9-step plan keys + ≥5 search queries
2. Decision `HOLD` required before `check_edit_safe`
3. `REOPEN` → fix plan steps → refute again

This is a forced brain loop, heavier than empty think notes — still lighter than `/view`.

## Repair wake (HARD — after verify/probe/hollow fail)

If `verify_bundle` fails, `fault_probe` has survivors, or `hollow_surface` is unclean:

1. Optional: `gk_code.self_heal` for tool traceback fallback (does **not** clear the gate)
2. `ultradeep_repair_wake` with diagnosis (≥40 chars, real words) + ≥3 unique hypotheses
3. If the fix changes the 9-step plan: `touches_plan=true` and plan_refute must be HOLD
4. Then edit → `verify_bundle` again (clears wake only on green)

Streak ≥3 → escalated (council/swarm before more edits).

## Token discipline during edit
One file per turn. Surgical recon (`map`/`search`/`preview`) for that file — not whole-tree `read_all`.
`read_all` defaults are capped; raise max_files / max_chars_per_file only when needed.
Call GODKILLER gates at phase boundaries (start/verify/claim), not `status`/`activate` every tiny edit.
Peers on demand. **UI:** console+network (`chrome-devtools`) before screenshot/`visual_step` loops. Forbidden: maximal tool swarm every turn.

## Posture (all modes)

Pessimistic + win USER goal. Capability gap → `tool_propose` (5–10) → `tool_approve` OR `tool_reject_all` → `tool_used` if approved. **Never silent install.**
