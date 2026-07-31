---
name: view-protocol
description: Bundled /view — adversarial research planning (weaknesses-only).
---

# Trigger Command: `/view`

Research **planning** only. No application code edits.

## Contract

- Agent proposes; harness seals.
- Praise / balanced review = Seal fail.
- Gravity G1–G4 = scale of work (not a calendar). One heavy refute wake after draft plan.

## Pipeline (forced)

1. `activate_mode({mode:"view", goal, open_kernel_task:true})`
2. `gk_mode.view_start` — goal + gravity
3. `view_search` × N (G1≥12 … G4≥30) — each with real `http(s)` URL or `doi:`
4. `view_attack` × K — each: quote ≥20 + doi_or_url + locator + stance + taxonomy + severity  
   - DOI cites: live resolve (unless `GODKILLER_DOI_RESOLVE=0`); quote must bind to title/abstract **or** `page_excerpt` must contain the quote (`GODKILLER_QUOTE_BIND`).
   - DOI must **resolve** via Crossref/OpenAlex unless `GODKILLER_DOI_RESOLVE=0` (shape-only offline)
5. `view_draft` — full Plan OS 9 steps, adversarial content (autopsy / outcompete)
6. **Alarm:** `view_refute` ≥20–30 findings **attacking the plan** → HOLD | REOPEN | KILL
7. `view_finalize` — weaknesses-only report ≥200 chars
8. Optional: `gk_meta.plan_validate` with sealed steps before leaving to code modes

## Forbidden

- Claiming done from chat
- Seal without HOLD refute
- inventing URLs / “from training memory”

## Posture (all modes)

Pessimistic + win USER goal. Any capability gap → `tool_propose` (5–10 public candidates after host search) → `tool_approve` OR `tool_reject_all` → `tool_used` if approved. **Never silent install.**
