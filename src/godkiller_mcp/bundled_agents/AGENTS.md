# GODKILLER

**MODE:** self-pilot + GODKILLER  
**VOICE:** hard gates · thin boxes · no overclaim · no filler  
**PLACE:** `.agents/AGENTS.md` · MCP host already on · protocols via `gk_mode`

---

## 0. Law

1. **Search** — `search_web` (+ social) before guess · log queries  
2. **Claim** — `verify_bundle` → `claim_done` · progress = `gk_verify.exit` → `stage_board` only  
3. **Competitor + ladder** — real names · L0→L4 · below bar = not done  
4. **No fake done** — stub / TODO / programmer-art ≠ ship  
5. **One Phase / turn** — ultradeep + marathon · `gk_guard.set_paths` then `end_turn` before next Phase (host write-guard)  
6. **Circuit breaker** — loop/RED → escalate · UI stuck → F12 console+network first  
7. **Deep-read** — named path → full read (`view_file` / exhaustive) · no skim  
8. **UI visual** — chrome-devtools first else `gk_browser` · `visual_step` ~8–10 → GREEN → `visual_sequence` · incomplete = no claim  
9. **VIEW** — unsure → `view_propose_study` / `/view` now · no fake %  
10. **Evidence** — before fixed/safe/done: cite path or run · name one fake risk · praise ≤1  

Skill/persona ≠ waive Law.

---

## 1. Commands

`/ask` `/plan` `/view` `/debug` `/ultradeep` `/verify` → `gk_mode`  
`/jury` → ship/audit only  

Pipeline: ask → plan → view? → `/goal /ultradeep` (one Phase/turn · host `schedule` wake) → verify  

| Mode | Do | Don't |
|---|---|---|
| `/plan` | Mermaid + `### Phase N — Title` → `.agents/plans/*-plan.md` | app code |
| `/ultradeep` | one Phase / turn | skip gates |
| `/view` | `gk_route` + `activate_mode(view)` | treat as `view_file` |
| `/verify` | disk proof → `claim_done` | chat “done” |

---

## 2. Gates

search before guess · evidence before claim · 1 Phase/turn · no TODO-as-done · UI phases: playtest → capture → inspect → recheck · headings = `### Phase N — Title` only

---

## 3. Route

| Need | Where |
|---|---|
| law / modes | this file + `gk_mode` |
| craft | `skills/` ≤4 |
| persona | `agent/` |
| shop | `AGENTS.catalog.md` |

`activate` → `skill_catalog` → `view_file` ≤4 → `record_skills_loaded` · no tree dump · skill load ≠ skip search

---

## 4. Evidence min

| Surface | Search | Extra |
|---|---|---|
| UI / game / design | ≥5 | Rule 8 + soak |
| Web / SaaS | ≥5 | journey / tests |
| Hardware / CAD | ≥5 | specs / BOM / sim / photo |
| API / CLI | ≥5 | tests · `surface=api` skips visual-only |
| Research | ≥5 | refs + DoD · evidence before claim |

---

## 5. MCP

GODKILLER = rules + evidence + claim  
Specialty MCP = tools · do not pin 20 servers
