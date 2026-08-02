# GODKILLER MCP

**Beta MCP proof-kernel** for agent IDEs (Antigravity / Cursor / Claude Desktop).  
Plan. Gate. Prove on disk. Then `claim_done` — or get blocked.  
Chat is never status. The harness decides.

```text
call MCP tools → gates on disk → claim_done | blocked
native Write/Edit/Terminal → NOT intercepted (unless host PreToolUse)
```

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/taurus42119-stack/godkiller-mcp/actions/workflows/ci.yml)

**Contact:** [Instagram @Kayvin.th](https://instagram.com/Kayvin.th)

---

## What this is / is not (read once)

| Claim | Truth |
| --- | --- |
| Proof-or-block on **GODKILLER tool calls** | Yes — disk evidence, seals, exit checklist |
| Intercepts native IDE Write/Edit | **No** — unless host wires PreToolUse → `godkiller-write-guard` |
| OS lockdown / Enterprise / SSO / multi-tenant SaaS | **No** — local single-process MCP |
| Makes a small model smarter than Opus on every task | **No** — wins on long UI/game/discipline; not short oracle puzzles |
| Beats Bare agent on Isolated/World pytest oracles | **Not proven** — treat as tie unless your A/B scorecard says otherwise |
| Free on PyPI / GitHub (MIT) | Yes — fork, modify, redistribute with license notice |

**Mouth:** harsh inside the MCP circle. Weak on agents that skip ritual and use native Write.  
Full stack harshness = `PROFILE=ship` + workspace pin + seal + **proven** write-guard. See [`docs/HOST_VS_MCP.md`](docs/HOST_VS_MCP.md).

---

## Install (60 seconds)

```bash
pip install godkiller-mcp
# optional: pip install 'godkiller-mcp[browser]' && playwright install chromium
```

Generate a seal key (do not commit):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### MCP host config (Cursor / Claude / Antigravity)

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp",
      "env": {
        "GODKILLER_PROFILE": "ship",
        "GODKILLER_WORKSPACE": "/absolute/path/to/your/project",
        "GODKILLER_HOME": "/absolute/path/to/your/project/.godkiller-session",
        "GODKILLER_SEAL_KEY": "REPLACE_WITH_64_HEX",
        "GODKILLER_SEAL_REQUIRE_ENV": "1"
      }
    }
  }
}
```

Alternate entry: `python -m godkiller_mcp.server`.

**One HOME per concurrent host.** Sharing `GODKILLER_HOME` races on tasks/evidence (`tasks.lock` is advisory only — not multi-tenant).

---

## Ship checklist (hardened local posture)

```bash
export GODKILLER_PROFILE=ship
export GODKILLER_WORKSPACE="/path/to/project"
export GODKILLER_HOME="/path/to/project/.godkiller-session-$USER"
export GODKILLER_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export GODKILLER_SEAL_REQUIRE_ENV=1
# 1) Wire PreToolUse → godkiller-write-guard --stdin   (docs/WRITE_GUARD_HOOKS.md)
# 2) Live deny/allow test
# 3) ONLY THEN:
export GODKILLER_WRITE_GUARD_PROVEN=1
```

| Flag | Effect |
| --- | --- |
| `PROFILE=ship` | Ignores `DEV_RELAX`; `claim_done` / `exit` require `WRITE_GUARD_PROVEN` |
| Without `PROVEN` | Native Write still bypasses MCP; ship **claim** stays blocked on gate `write_guard` |
| Empty PROFILE | Armor still mostly on (`ship_mode()`), but **not** the declared ship posture |
| `DEV_RELAX=1` | Soft gates — local experiments only (blocked under `PROFILE=ship`) |

Optional: `godkiller-write-guard install --target cursor` then wire PreToolUse.  
Host last word outside the agent story: `python -m godkiller_mcp.prove` / `godkiller-prove`.

---

## Intensity layers (honest)

| Layer | Intensity | Meaning |
| --- | --- | --- |
| Tool entry | Med–high | ~13 facades; `gk_meta.status` first; wrong action → `allowed:[…]` |
| Search / edit | High on MCP path | Bugfix: **search (≥3) → blast_radius → edit_safe** |
| Dump / read_all | Gated | Needs symbol intel first (jcodemunch digest / `gk_code.map` / `search` + `task_id`) |
| Finish / claim | Very hard | verify · freshness · hollow · fault_probe · exit · council refute · swarm · ship write_guard |
| Native Write | Weak until proven | `hook_hint_only` until operator sets `WRITE_GUARD_PROVEN=1` after live PreToolUse |
| `/debug` | Signal only | Static scan + token heuristics — **not** a live debugger |
| `gk_scan` | Heuristic | Not professional SAST |

---

## MANDATORY — agent orders

If the host lists a **godkiller** MCP server, obey this list:

1. **First tool:** `gk_meta.status` — if it fails, stop. Do not invent that the kernel is live.
2. **Before edits:** `gk_task` / `gk_phase` (plan → localize → fix). Native Write alone = protocol violation on WITH arms.
3. **Bugfix:** record search evidence → `blast_radius` → `edit_safe`. Chat “I searched” does not count.
4. **Before dump-all:** jcodemunch / codebase-memory **or** `gk_code.map`/`search` with `task_id`, or pass `symbol_digest=…` (≥24 chars).
5. **Before done:** `gk_verify.exit` → `directive: pass` → `gk_phase.claim_done`. Chat “tests passed” ≠ done.
6. **Disk proof:** run must leave `.godkiller/` (or `GODKILLER_HOME`). No state dir ⇒ you did not use the kernel.
7. **Never** invent tool names, scores, GREEN, or “beats Bare on oracle.”

Plan templates inject **fail recipes** from prior verified failures (`task_passed=0`) — not praise, not confidence%.

```text
goal → mode → plan (+ fail recipes) → search/blast → gated edit
    → disk verify → hollow → probe → exit_checklist → claim_done|blocked
```

---

## Facades (kernel surface)

| Facade | Job |
| --- | --- |
| `gk_meta` | Honesty status · 9-step plan template/validate |
| `gk_route` | `/ask` `/plan` `/debug` `/ultradeep` `/view` `/verify` |
| `gk_task` | open · hypothesize · blast · edit_safe · failing_slice |
| `gk_phase` | assert · claim_done · rubric |
| `gk_evidence` | shots · visual_step · critic · journey |
| `gk_verify` | bundle · hollow · probe · exit (stage_board) · soak |
| `gk_memory` | lessons · marathon · graph · what_blocked |
| `gk_code` | map · search · read_full · council · swarm · pipeline |
| `gk_guard` | write allowlist brain for host PreToolUse |
| `gk_scan` | heuristic CWE / optional semgrep |
| `gk_browser` | Playwright **fallback** — blocked when host lists `chrome-devtools` (use that peer first) |
| `gk_mode` | protocols · skills · ultradeep · debug_engine · tool_propose |
| `gk_handoff` | spec/feedback gates |

**Pair specialty MCPs as brains; GODKILLER as judge.** Prefer jcodemunch / codebase-memory for symbols — do not use exhaustive dump as default search.

---

## Kernel armor (what actually bites)

| Gate | Behavior |
| --- | --- |
| Phase machine | Illegal Antigravity phase skips blocked |
| Plan OS | 9-step validate; UI plans need playtest→capture→inspect→recheck |
| Edit safety | blast + path sandbox (`GODKILLER_WORKSPACE`) + bugfix route |
| Verify | allowlisted pytest/unittest/… · `result_digest` · **material_hash freshness** |
| Hollow | Python AST + web + Go/Rust/… markers; non-Py = heuristic warn |
| Fault probe | Mutants in **shadow temp** — SIGKILL cannot leave mutants in live tree |
| Exit | `gk_verify.exit` → short `stage_board` before claim |
| Claim | `status: done\|blocked` + `gate` — harness decides |
| Seal | HMAC on armor evidence — forge JSON on disk gets scrubbed |
| Council | Hacker REJECT-first; host theatre labeled; ship blocks host council unless `ALLOW_HOST_COUNCIL` |
| Write guard | Hint until `PROVEN`; ship claim blocks without it |

**Not claim-grade:** regex “security scan”, readiness%, host council theatre, competitor URL advisory, soak without command.

---

## Threat model (local MCP bar)

| Attack | Result |
| --- | --- |
| MCP read/write outside workspace | `path_outside_workspace` |
| Handoff/marathon `../` slug | illegal slug |
| Native Write jailbreak | **Passes** until PreToolUse proven — by design |
| Shared `GODKILLER_HOME` across processes | Race — use one HOME per session |
| Forge sealed evidence JSON | Seal scrub / claim still blocked |
| Prompt injection via skill MD | Skills are indexed and fed back — host trust problem, not kernel execution of skill as code |

Full notes: [`SECURITY.md`](SECURITY.md) · [`docs/SEAL_KEY.md`](docs/SEAL_KEY.md) · [`docs/WRITE_GUARD_HOOKS.md`](docs/WRITE_GUARD_HOOKS.md).

---

## Modes

| Mode | Contract |
| --- | --- |
| `/ask` | No application edits |
| `/plan` | 9-step before build |
| `/debug` | Repro + hypothesis; signal loop ≠ debugger |
| `/ultradeep` | One file think→plan→edit; refute wake before edit_safe |
| `/view` | Study patterns — do not paste whole repos as “done” |
| `/verify` | Proof → claim_done |

Skills: `gk_mode.skill_catalog` — load **≤4** JIT skills per task. Dumping 200 skills = dumber agent.

---

## Arena / A/B (optional proof — not marketing)

Internal Isolated/World volume oracles: **Bare ≈ WITH** on pass counts is an honest baseline.  
Craft/discipline gains show more on long UI / game / marathon work.  
Protocol: [`benchmarks/MEGA_AB_PROTOCOL.md`](benchmarks/MEGA_AB_PROTOCOL.md) · score with `score_11` / game / world — not chat vibes.

```powershell
$env:GODKILLER_ARENA_ROOT="<arena-root>"
python -m benchmarks.reset_arena
# Bare arm then WITH arm — same prompt, no oracle cheat
python -m benchmarks.score_11 --compare
```

Engine gauntlet + package tests: `pytest -q` (CI collects **~610** tests; count drifts as suites grow).

---

## Repo layout (Beta tree)

**Ship these (GitHub tag + Desktop แจก):**

| Path | Why |
| --- | --- |
| `src/godkiller_mcp/` | Product |
| `tests/` | Regression peel |
| `docs/` | Contracts linked from README/SECURITY (`HOST_VS_MCP` · `WRITE_GUARD_HOOKS` · `SEAL_KEY`) |
| `.github/` | CI / publish / scorecard |
| `.agents/` | Host constitution (`gk_meta.status` → `agents_md`) |
| `pyproject.toml` · `MANIFEST.in` · `README.md` · `LICENSE` · `SECURITY.md` · `CHANGELOG.md` · `.gitignore` | Package |

**Never ship:** `.godkiller/` (runtime envelopes — machine paths + HMAC) · `*.egg-info/` · `__pycache__/` · `.venv/` · local `.env` / seal files.

---

## Security (short)

- Secret **values** never returned over MCP (names only)
- Prefer `shell=False` · verify command allowlist
- Server-authored forge-resistant evidence: `PASSING_TEST` / `BLAST_RADIUS` / `EDIT_SAFE`
- Network scrape/browser = explicit opt-in extras
- Pin `GODKILLER_WORKSPACE` — unpinned `$HOME` cwd refused

Reports: [GitHub Security Advisories](https://github.com/taurus42119-stack/godkiller-mcp/security/advisories/new)

---

## License

MIT © 2026 GODKILLER Team — [LICENSE](LICENSE)
