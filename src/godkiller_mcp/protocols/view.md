---
name: view-protocol
description: Bundled /view — adversarial research planning (weaknesses-only).
---

# Trigger Command: `/view`

Research **planning** only. No application code edits.

## [CRITICAL — NOT `view_file`]

Slash `/view` = this adversarial protocol. IDE tool `view_file` ≠ `/view`.
First tools must be `gk_route` / `activate_mode(view)` / `view_start` — not “I read geometry.js, plan looks OK.”

## Contract

- Agent proposes; harness seals.
- Praise / balanced review = Seal fail.
- Gravity G1–G4 = scale of work (not a calendar). One heavy refute wake after draft plan.

## Pipeline (forced)

0. **If confidence < 99%:** `gk_mode.view_propose_study` **immediately** — propose in chat which public repos/files to deep-read (copy-study). Do not silently invent.
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

## Example hunt (copy-study)

- Goal: learn file layout / API from a **public reference repo**, then adapt.
- Allowed: deep-read exemplar files; cite what you will change.
- Forbidden: paste an entire foreign repo and claim the task done.

## Forbidden

- Claiming done from chat
- Seal without HOLD refute
- inventing URLs / “from training memory”

## Posture (all modes)

Pessimistic + win USER goal. Any capability gap → `tool_propose` (5–10 public candidates after host search) → `tool_approve` OR `tool_reject_all` → `tool_used` if approved. **Never silent install.**
