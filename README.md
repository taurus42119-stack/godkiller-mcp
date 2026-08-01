# GODKILLER MCP

Phase kernel for **Google Antigravity** (MCP tools + disk proof).  
Plan. Gate. Prove on disk. Then claim done — or get blocked.

**Threat model (honest):** this package controls what happens **when the agent
calls GODKILLER tools**. It does **not** intercept native IDE Write/Edit/Terminal.
Those bypass MCP unless a **host PreToolUse hook** (or companion guard) wraps them —
see `docs/HOST_VS_MCP.md` and `docs/WRITE_GUARD_HOOKS.md`.
Without that hook, GODKILLER **does not enforce** native Write — only MCP tool calls.
Chat ceremony ≠ execution boundary.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml)

```bash
pip install godkiller-mcp
# host Write lock: wire PreToolUse → godkiller-write-guard --stdin
# (see docs/WRITE_GUARD_HOOKS.md) — without this hook, native Write bypasses MCP
```

**Status:** Beta MCP proof kernel — not Enterprise Ready / not OS lock / not Production-Stable / not multi-tenant SaaS (no SSO, SIEM, or 100k shared-backend claims).  
**Honest mouth:** call `gk_meta.status` (`gk_honesty_status`) for disk MCP configs + real facades — trust that JSON over chat memory. Never invent tools/servers/scores.  
**Host boundary:** native IDE Write/Edit bypass MCP unless PreToolUse → `godkiller-write-guard` is wired (`docs/WRITE_GUARD_HOOKS.md`). Without that hook, treat Write as unrestricted.  
**Internal A/B (honest):** on Isolated/World volume oracles, Bare ≈ WITH pass counts — MCP is not proven to raise pytest score; craft/discipline gains show more on long UI/game work. Do not claim “beats Bare on oracle” from chat.  
**Skills power-up:** `gk_mode.skill_catalog` merges project `.agents/skills` + **agent-ops** (bundled). Forced routes for review / babysit / automate / create-skill / shell.  
**Paired `.agents`:** `gk_meta.status` returns `agents_constitution` with `must_read_agents_md` + path to `AGENTS.md` (Supreme Law). Set `GODKILLER_AGENTS_MD` / `GODKILLER_AGENTS_ROOT` so every host points at the same constitution.  
**Free tier:** this MCP (proof-or-block on GODKILLER tool calls) is free on PyPI/GitHub.  
**Not free:** 24-hour automation loops / deep host control — for serious interest only (not shipped in this package).  
**Security reports:** [GitHub Security Advisories](https://github.com/taurus42119-stack/godkiller-mcp/security/advisories/new) (see `SECURITY.md`).

---

## MANDATORY — agent orders (non-negotiable)

If the host has a **`godkiller` MCP server**, you **MUST** use it. Soft “I will plan in chat” is **not** enough.

1. **FIRST tool call** after reading the task: `gk_meta.status` (or honesty/status action).  
   If this fails, stop and report — do not pretend the kernel is active.
2. **BEFORE any file edit:** open/advance work via `gk_task` / `gk_phase` (plan → localize → fix).  
   Native Write/Edit alone = **protocol violation** on WITH arms.
3. **Search / evidence:** satisfy GODKILLER search gates when the phase requires them. Do not invent “I searched.”
4. **BEFORE claiming done:** `gk_verify` (bundle / exit checklist) then `gk_phase.claim_done` (or equivalent).  
   Chat “516 passed” without server `directive` / sealed result = **not done**.
5. **Disk proof:** workspace **MUST** contain `.godkiller/` after the run.  
   No `.godkiller/` ⇒ you did **not** use the kernel — do not claim MCP-assisted success.
6. **Never** invent tool names, scores, or “GREEN” without tool JSON on disk.

README text is still soft without a host PreToolUse hook — but **WITH / A/B agents are ordered to obey this list anyway**.  
Hard host PreToolUse lock (if the IDE calls it): wire `godkiller-write-guard` — see `docs/WRITE_GUARD_HOOKS.md`. Not an OS MAC / kernel lockdown.

---

## Quick MCP config

Claude Desktop / compatible MCP hosts (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "python",
      "args": ["-m", "godkiller_mcp.server"],
      "env": {
        "GODKILLER_PROFILE": "ship",
        "GODKILLER_SEAL_KEY": "REPLACE_WITH_64_HEX_FROM_secrets.token_hex_32"
      }
    }
  }
}
```

Generate a seal key once: `python -c "import secrets; print(secrets.token_hex(32))"`.  
Do not commit the key.

## Mission

Inside MCP: the agent cannot get `status: done` without server-side proof.  
Outside MCP: native Write can still change files — **do not treat MCP alone as OS control**.

**Contract:** the agent may *propose* done — the harness *decides*.  
Chat summary is never status. Only `claim_done` / `prove` / `exit_checklist` with a green directive counts.

| Agent failure | Why | Kernel force |
| --- | --- | --- |
| Won’t quit / says done while broken | model wants to end the turn | `claim_done` → `status: blocked` + `gate` |
| Trusts terminal / stale “passed” | self-report or old logs | server verify + `result_digest` + **freshness** |
| Confidence from shallow green | tests miss real bugs | **fault_probe** — survivors = cannot claim |

**Ship hardening profile (MCP proof kernel):**

```bash
export GODKILLER_PROFILE=ship
export GODKILLER_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export GODKILLER_SEAL_REQUIRE_ENV=1
# + host PreToolUse → godkiller-write-guard  (docs/WRITE_GUARD_HOOKS.md)
```

This is the **ship deployment posture** for proof-or-block on MCP tools:
ship armor, host-only seal, write hook. It is **not** Enterprise Ready, SSO/DLP, or full-IDE OS lock —
see `SECURITY.md` and `docs/HOST_VS_MCP.md`.

**Ship profile:** set `GODKILLER_PROFILE=ship` so even `GODKILLER_DEV_RELAX=1` cannot disarm armor.  
Without ship: `DEV_RELAX=1` softens gates (local experiments only) — the server prints a stderr warning when relax is active.

Static `gk_scan.security` is an **AST/heuristic signal** (optional Snyk/Bandit if on PATH), not a professional SAST / security audit.  
Council must record a Hacker `REJECT` before `COUNCIL_PASS` (nits-only = theatre).

**Seal key:** require host `GODKILLER_SEAL_KEY` (see [`docs/SEAL_KEY.md`](docs/SEAL_KEY.md)); no silent `.seal_key` mint.  
**Write enforce:** only with host PreToolUse — demo in [`docs/WRITE_GUARD_HOOKS.md`](docs/WRITE_GUARD_HOOKS.md).  
**Arena WITH (dims 5–11):** set `GODKILLER_ARENA_ARM=…/2_WITH_MCP` before `scripts/sync_mcp_with.ps1` so `GODKILLER_HOME` lands on the arm; use the same `GODKILLER_SEAL_KEY` for agent + `python -m benchmarks.score_11` (see `benchmarks/MEGA_AB_PROTOCOL.md`).

Preflight: `gk_verify.exit` → `exit_checklist` (`directive: pass|reject`).  
Host last word: `python -m godkiller_mcp.prove`.

| Failure mode | Kernel response |
| --- | --- |
| No `/plan` | plan / phase gates |
| Multi-file rush | `/ultradeep` one-file think → plan → edit |
| Fake “done” | `verify_bundle` + `claim_done` block (server-authored evidence only) |
| Session amnesia | marathon + memory graph |
| Weak review | LLM council — Coder / Hacker / Optimizer, multi-round debate |

```text
goal → mode → evidence/plan → gated edit → disk verify → probe → exit_checklist → claim_done|blocked
```
---

## Arena — Antigravity A/B (the real proof)

Pre-solved twins that both pass 516 prove nothing. The honest protocol:

1. Reset arms to sealed buggy `1_ORIGINAL`
2. You open **Antigravity** on `3_WITHOUT_MCP` with MCP **off** → agent tries → we score
3. Reset / open `2_WITH_MCP` with MCP **on** → agent tries → we score
4. Compare **11 dimensions** (fail-closed on missing evidence)

| Control | Value |
| --- | --- |
| Arena root | `GODKILLER_ISOLATED_ARENA` / `GODKILLER_ARENA_ROOT` |
| Baseline | `1_ORIGINAL` (never edit mid-run) |
| Bare | `3_WITHOUT_MCP` |
| GODKILLER | `2_WITH_MCP` |
| Oracle | sealed `hidden_oracle/` |
| Protocol | [`benchmarks/ANTIGRAVITY_AB_PROTOCOL.md`](benchmarks/ANTIGRAVITY_AB_PROTOCOL.md) |

### 11 dimensions

| # | Dimension |
| ---: | --- |
| 1 | Code correctness (oracle pass %) |
| 2 | Oracle volume (≥516 collected) |
| 3 | Output integrity (full pytest body) |
| 4 | Delta from baseline (files actually changed) |
| 5 | Reconnaissance / exhaustive read artifacts |
| 6 | Phase discipline (task / plan / marathon) |
| 7 | Blast radius + edit-safe |
| 8 | Verify bundle + claim_done |
| 9 | Council (Coder / Hacker / Optimizer) |
| 10 | Security hardening signals |
| 11 | UI visual gate (critic / screenshots) |

```powershell
$env:GODKILLER_ARENA_ROOT="<your-arena-root>"
python -m benchmarks.reset_arena
# → open Antigravity bare, then:
python -m benchmarks.score_11 --arm 3_WITHOUT_MCP
# → open Antigravity + MCP, then:
python -m benchmarks.score_11 --arm 2_WITH_MCP
python -m benchmarks.score_11 --compare
```

Scorecard lands under `$env:GODKILLER_ARENA_ROOT\logs\` after *your* runs — not a fake pre-fill.

### Game arena (Three.js FPS — Field 3)

Separate root from Isolated. Machine score is `score_game` (build / boot / playable / FPS≥60 / adaptive / pixel). Beauty is human eyes via `game/OPEN.md`.

| Arena root | `GODKILLER_GAME_ARENA` / `GODKILLER_GAME_ARENA_ROOT` |
| Protocol | Desktop `GODKILLER_GAME_ARENA/GAME_AB_PROTOCOL.md` |

**Mega campaign (Isolated 516 + World 1000 + Game):** [`benchmarks/MEGA_AB_PROTOCOL.md`](benchmarks/MEGA_AB_PROTOCOL.md) · `python -m benchmarks.mega_scorecard`

```powershell
$env:GODKILLER_GAME_ARENA_ROOT="$env:USERPROFILE\Desktop\GODKILLER_GAME_ARENA"
python -m benchmarks.reset_game_arena
python -m benchmarks.score_game --arm 3_WITHOUT_MCP
python -m benchmarks.score_game --arm 2_WITH_MCP
python -m benchmarks.score_game --compare
```

Stub ships with `mode: "stub"` so `hard_pass` stays false until the agent builds a real game (`mode` ≠ `stub`).

### World arena (Field 2 — volume ~1000)

```powershell
$env:GODKILLER_WORLD_ARENA_ROOT="$env:USERPROFILE\Desktop\GODKILLER_WORLD_ARENA"
python -m benchmarks.world.import_hard_volume --target 1000
python -m benchmarks.reset_world_arena
python -m benchmarks.score_world --arm 3_WITHOUT_MCP
```

Mouth: internal hard volume A/B — **not** an official LiveCodeBench leaderboard claim (see arena `ATTRIBUTION.md`).

### Engine gauntlet (in-package kernel proof)

| Gate | Load |
| --- | --- |
| Kernel forge/skip | adversarial + volume matrix |
| Phase illegal jumps | full forward-skip matrix |
| Verify allowlist | allow + deny command grids |
| Council host tally | all 8 vote combinations |
| Exhaustive read | 120 size variants (incl. >3000 chars) |
| Closed-task immutability | 80 variants |
| Package suite | **469** passed (`pytest -q` — see CI) |

```bash
python -m benchmarks.run_arena --mode engine
pytest -q
```

---

## Kernel

| Layer | Enforcement |
| --- | --- |
| Phase machine | `assert_phase` / `claim_done` |
| Plan OS | 9-step validate before fix edits |
| Edit safety | blast radius + path-safe `check_edit_safe` |
| `/ultradeep` | one phase/turn · one file/edit cycle |
| Verify | disk · `result_digest` · **`material_hash` freshness** · fault_probe |
| Exit checklist | `gk_verify.exit` → `directive: pass\|reject` before claim |
| Claim | `status: done\|blocked` + `gate` — agent proposes, harness decides |
| Ship profile | `GODKILLER_PROFILE=ship` ignores `DEV_RELAX`; default ship-like without relax |
| Critic-proof | no LOG-forge · workspace freshness · lint ≠ claim · vacuous probe/hollow fail |
| Anti-hype | hollow TS/JS/UI · **exit_checklist before claim** · council **refute-first** · soak needs command |
| Critic hunt | probe allowlist · targets under workspace · workspace hash · seal vs JSON forge · deeper mutants |
| Host prove | `python -m godkiller_mcp.prove` — re-verify outside agent self-report |
| Not claimed | native IDE Write lock without host hook — use `gk_guard` + `docs/WRITE_GUARD_HOOKS.md` |
| Write guard | `gk_guard.write` / `python -m godkiller_mcp.write_guard` for PreToolUse |
| Swarm | `gk_code.swarm_*` — scout/attacker/planner/verifier (host or API parallel) |
| `/view` | Adversarial research plan: hunt→attack→9-step→refute wake→seal (DOI live resolve) |
| Ultradeep wake | `ultradeep_plan_refute` required after plan_validate before edit_safe |
| Repair wake | `ultradeep_repair_wake` after verify/probe/hollow fail — self_heal still tool-fallback |

| Hollow surface | unfinished bodies blocked before `claim_done` |
| Plan lock | write-through-plan — 9-step validate before edit/claim |
| Session ledger | hash chain under `.godkiller/session_ledger.jsonl` |
| Strict mode | `GODKILLER_STRICT=1` — privileged tools need `task_id` |
| Council | host debate (default) · optional API |
| Visual critic | **pixels required** — regex alone cannot GREEN |
| Recovery | self_heal = traceback parse → one fallback tool run |

```text
goal → mode → evidence/plan → gated edit → disk verify → hollow → claim_done
```

### `/ultradeep`

`queue` → `think` (≥3 hypotheses) → `plan` → `edit_safe` (1 path) → verify → `advance`

### Council

**Host mode (default):** MCP sends Coder / Hacker / Optimizer role briefs to the IDE model → `council_submit` → `council_finalize`  

**API mode (optional):** `GODKILLER_LLM_API_KEY` / `OPENAI_API_KEY` + `mode=api`

---

## Install

```bash
pip install godkiller-mcp
# pip install 'godkiller-mcp[browser]' && playwright install chromium
# pip install 'godkiller-mcp[scrape]'
# optional OCR: pip install pytesseract  (+ Tesseract binary)
```

```json
{
  "mcpServers": {
    "godkiller": { "command": "godkiller-mcp" }
  }
}
```

Alternate: `python -m godkiller_mcp.server`  
Optional: `GODKILLER_HOME` · `GODKILLER_TOOLS_DIR` · `GODKILLER_LLM_API_KEY`

---

## Tools — Kernel vs recovery vs experimental

**Kernel (the product):** `gk_route` · `gk_mode` · `gk_task` · `gk_phase` · `gk_evidence` · `gk_verify` (bundle / hollow / **probe** / ledger) · `gk_memory` · `gk_code` (map / search / read_full / council*) · `gk_meta` (plan)

**Recovery:** `gk_code.self_heal` · `gk_code.pipeline`

**Optional / experimental:** `gk_browser` · `gk_scan` · `gk_handoff` · scrape · skillify · confidence · auto_fix · soak / competitor

Env: `GODKILLER_PLAN_LOCK=1` (default) · `GODKILLER_FAULT_PROBE=1` (default) · `GODKILLER_STRICT=1` (opt-in) · `GODKILLER_DEV_RELAX=1` (local soft bypass only)

---

## Modes

| Mode | Contract |
| --- | --- |
| `/ask` | no application edits |
| `/plan` | 9-step before build |
| `/debug` | repro + hypothesis before fix |
| `/ultradeep` | marathon · max tools · per-file gate |
| `/verify` | proof → claim_done |

---

## Security

- Secret values never returned over MCP (names only)  
- Prefer `shell=False` verify/soak · verify command allowlist  
- Forge-proof evidence types: `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE`  
- Network scrape/browser are explicit invocations  

State lives under `GODKILLER_HOME` or `<cwd>/.godkiller/`.

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
