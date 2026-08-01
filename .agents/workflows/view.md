---
name: view-protocol
description: Triggers when user types '/view'. Adversarial Research Planning — NOT plain file reading.
---

# Trigger: /view

When `/view` is invoked, **immediately** enter **Adversarial Research Planning Mode**.

## [CRITICAL — NOT `view_file`]

| Token | Meaning |
|---|---|
| **`/view`** (slash command) | GODKILLER **mode**: hunt → attack plan → refute → seal. Use `gk_route` + `gk_mode.view_*` |
| **`view_file`** (IDE tool) | Just open a file. **Does NOT satisfy `/view`.** |

**FORBIDDEN first response to `/view`:** only calling `view_file` / reading one local file / saying “I inspected the plan, looks OK.”

**REQUIRED first tools:** `gk_route.classify` (or equivalent) → `gk_mode.activate({mode:"view", …})` → `gk_mode.view_start` (or `view_propose_study` if confidence &lt; 99%).

## [WORLD KERNEL — ADDITIVE GATES]

If MCP `GODKILLER` is available, ALSO:
1. `gk_route.classify` on the user message containing `/view`.
2. `activate_mode({mode:"view", goal, open_kernel_task:true})` and **follow the protocol markdown returned**.
3. Pipeline (forced):
   - confidence &lt; 99% → `view_propose_study` first (copy-study repos/files)
   - `view_start` (goal + gravity G1–G4)
   - `view_search` × N with real `http(s)` / `doi:` (G1≥12 … G4≥30)
   - `view_attack` × K (quote + URL/DOI + stance + severity)
   - `view_draft` — full 9-step adversarial plan
   - `view_refute` ≥20–30 attacks on **the plan** → HOLD | REOPEN | KILL
   - `view_finalize` — weaknesses-only report ≥200 chars
   - optional `gk_meta.plan_validate` (with `### Phase N` headings) before `/ultradeep`
4. **No application code edits** in `/view`. No `request_claim_done`.
5. Praise / “looks good / 100% aligned” without refute HOLD = **Seal fail**.

## [RELATION TO `/plan`]

- `/plan` = write the blueprint (phases, research log, architecture).
- `/view` = **stress-test / red-team that blueprint** (or research a sealed adversarial plan) before coding.
- User may say `/view` after `/plan` — still run the full adversarial pipeline; do **not** reduce it to re-reading local plan markdown with `view_file` alone.

## [ANTI-EXCUSE]

- **FORBIDDEN:** “`/view` means look at files.”
- **FORBIDDEN:** Skipping `gk_mode` because training memory already “knows” `/view`.
- Local `view_file` of `geometry.js` / `implementation_plan.md` is optional **evidence**, never a substitute for `view_start`…`view_finalize`.

## Hard brake

STRICTLY PROHIBITED from writing/editing application code (`.ts`, `.py`, game sources, etc.) under `/view`. Plan/research artifacts and GODKILLER evidence only.
