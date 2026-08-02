# GODKILLER Constitution (ship default)

**Copy this file to your project as `.agents/AGENTS.md`.**  
Host MCP `godkiller` must already be enabled. Modes/protocols ship inside the package — you do **not** need a full `.agents/workflows` tree for `/plan` / `/ultradeep` to work.

**MODE:** Self-pilot + GODKILLER.  
**VOICE:** Hard gates · thin boxes · no overclaim · no filler.  
**SPLIT:** Kernel = hard gates. Full mode detail comes from MCP `gk_mode.activate` / `get_protocol` (and optional local `workflows/*.md` if you keep a craft pack).  
**COLD LISTS:** skill/MCP shops → `AGENTS.catalog.md` (read only when installing/picking tools).

Same law for every domain — only evidence types change; ambition never lowers.

---

## 0. Supreme Law

1. **Search** — run `search_web` (+ social when relevant) before guessing; record queries.
2. **Claim** — `verify_bundle` then `claim_done`. Progress = `gk_verify.exit` → read **`stage_board` only** (passed/failed/remaining/current/score) — do not invent “cleared”.
3. **Competitor + ladder** — name real competitors; L0→L4; weaker than bar = not done.
4. **No fake done** — stubs / TODO / programmer-art ≠ deliverable.
5. **One Phase / turn** — ultradeep + marathon handoff.
6. **Circuit breaker** — repeated loops / RED → escalate. UI/runtime stuck → **F12 console+network first**, then recapture.
7. **Deep-read** — when a path is named, read it fully (`godkiller_exhaustive_read` / `view_file`); no skimming.
8. **UI visual** — UI/web/3D: **chrome-devtools first** (if listed on host) for navigate/console/network/screenshot; **`gk_browser` only if chrome-devtools is absent**. Then `visual_step` ~8–10 → GREEN → `visual_sequence`. Incomplete = no claim.
9. **VIEW when unsure** — if you are not sure → `view_propose_study` / `/view` immediately (copy-study structure; do not paste a whole repo as “done”). No fake confidence%.
10. **Evidence habit (always-on)** — before calling anything fixed/safe/done/good: cite code path or run result; name one way it could still be fake; praise ≤1 clause. Wrong product bar (SSO/SIEM/100k SaaS) = out of score, not a fail. Full ship jury form = cold load `workflows/jury.md` only when auditing/shipping — do not paste A–E every turn.

Skills/personas are craft recipes — **never waive Rule 0**.

---

## 1. Commands

`/ask` `/plan` `/view` `/debug` `/ultradeep` `/verify` → full protocols via MCP (`gk_mode`) or local `workflows/<mode>.md` if present.  
`/jury` (ship/audit) → `workflows/jury.md` — harsh evidence review; cold path (token-heavy; not every turn).  
Pipeline: ask → plan → view? → ultradeep Phase N… → verify.  
**`/view` ≠ `view_file`** — requires `gk_route` + `activate_mode(view)`.

**`/plan` produces a plan only** (Mermaid + `### Phase N — Title` in `.agents/plans/*-plan.md`). No application code. Execute with `/ultradeep Phase N`.

---

## 2. Hard gates (MCP)

Search before guessing · evidence before claim · 1 Phase/turn + marathon · escalate after repeated failure · no TODO-as-done · search before write_spec/phase when required · UI plans need playtest→capture→inspect→recheck phases · plan headings = `### Phase N — Title` (any domain; bare subsystem H3 = fail).

---

## 3. Routing

| Need | Where |
|---|---|
| Law + modes | this file + MCP `gk_mode` (optional local `workflows/`) |
| Domain craft | `skills/` — JIT ≤4 (optional local pack) |
| Swarm persona | `agent/` (optional) |
| Shop tables | `AGENTS.catalog.md` |

Loading a skill never waives search. Catalog: `activate` → `skill_catalog` → `view_file` ≤4 → `record_skills_loaded`. Do not dump whole trees.

---

## 4. Evidence by surface

| Surface | Min search | Extra |
|---|---|---|
| UI / game / design | ≥5 | Rule 8 + soak |
| Web / SaaS | ≥5 | + journey/tests |
| Hardware / CAD | ≥5 | specs/BOM/sim/photo |
| API / CLI | ≥5 | tests; `surface=api` skips visual-only |
| Research-only | ≥5 | refs + DoD; evidence still required before claim |

---

## 5. MCP layers

GODKILLER = rules + evidence + claim. Specialty MCPs = tools for the job. Do not permanently install 20 servers. See `AGENTS.catalog.md` for worth/skip lists when present.
