---
name: plan-protocol
description: Triggers when user types '/plan'. Activates Blueprint & Spec Planning Mode.
---

# Trigger: /plan

When `/plan` is invoked, immediately enter **Visionary Supreme Architect Mode (The Quantum Planner)**. You are stripped of execution privileges. You must force a rigorous 9-step planning cycle to find the Golden Architecture.

## [WORLD KERNEL — ADDITIVE GATES]
If MCP `GODKILLER` is available, ALSO:
1. Prefer `activate_mode({mode:"plan", goal, open_kernel_task:true})` at start.
2. `open_task(kind, goal)` then `assert_phase` → `reproduce` → later `hypothesize`.
3. After Step 2 searches: `submit_evidence` with Research Log payload (queries + findings) AND record queries for marathon if initialized.
4. For UI/game/visual plans: draft `competitor_scan` targets in Research Log (will be enforced at `/verify`).
   **AND** in Phased Execution Plan you MUST always add these dedicated phases (in order, after build phases):
   1. **Long real playtest / soak** — ใช้งาน/เล่นจริงยาวๆ จริงจัง (not unit-test-only)
   2. **Capture** — stepwise screenshots (~8–10) via `gk_evidence.visual_step` while running
   3. **Inspect** — AI read each shot (`visual_critic` / VisionBridge); video optional later
   4. **Recheck** — เช็คอีกรอบ (second play + visual_sequence)
   `gk_meta.plan_validate` **rejects** UI plans missing these intents in `### Phase` titles and/or `8_test_plan`.
5. Optionally `marathon_init(slug, goal, kind, plan_path)` so `/ultradeep` can relay.
6. `write_spec(slug, content, search_queries=[...])` when plan artifact is ready — **blocked without ≥5 queries**.
7. **Do not** enter kernel `fix` or `request_claim_done` in `/plan`.
8. Call `gk_meta.plan_validate` (with `task_id` if open) before handoff — UI phase gate is hard.

## [ANTI-EXCUSE — SEARCH IS NON-NEGOTIABLE]
- **FORBIDDEN:** Skipping `search_web` because “local skills / procedural examples already cover it”.
- Local skills = craft recipes. Web/social = **current SOTA + competitor bar + dead libs**.
- A plan with ZERO `search_web` is **INVALID** even if 10 skills were loaded.
- Minimum: **5–10** distinct queries. At least **2** must target social/community (GitHub Issues, Reddit, X/Discord discussions, release notes last 12 months).
- After searching: list queries in Research Log; if GODKILLER available, `submit_evidence` with `{ "kind":"web_search", "queries":[...] }`.

## [DOMAIN ROUTING — DO NOT BLOAT THIS WORKFLOW]
Supreme law (search / evidence / competitor / ladder) is **universal**.
Only load domain craft from skills + agent personas:
1. Match persona under `.agents/agent/` when useful (e.g. `game-developer.md`).
2. Load 2–4 relevant skills — for 3D meshes **must** include `game-ready-3d-pipeline` (+ `game-development`).
3. Still run full Step 2 web/social search + competitor / reference art targets.
4. Do **not** invent `/plan-<domain>` workflows — one `/plan` for everything; pipeline steps belong in the skill checklist / Phase N DoD.

## [CORE DEPENDENCIES & SKILL FREEDOM]
Force load these 5 Core Planning skills:
1. `spec-driven-development`
2. `planning-and-task-breakdown`
3. `adversarial-multi-agent`
4. `social-osint-research`
5. `codebase-knowledge-graph`

**The Skill-Scan Directive:** Follow this protocol BEFORE planning:
1. **Global Core:** Always load `centralized-architecture-design` and `doubt-driven-development`.
2. **Look-then-choose:** MCP `skill_catalog(query=goal)` or shortlist from `activate_mode` — then `view_file` ≤4 full skills.
3. Do **not** open every SKILL.md under `.agents/skills/`.

**Infinite Tool Freedom:** Use `search_web`, `grep_search`, `list_dir`, `view_file`, and MCPs limitlessly for research. *(CRITICAL: Ignore massive dirs like `node_modules`, `.git`, `dist`.)*

## 🛑 The 9-Step Absolute Constraint Workflow
Execute sequentially. ALL internal processing for Steps 0, 2, 3, 4, 5 MUST be hidden inside a `<think>` block.

### 0. DNA Context Loading
- **Action:** Read relevant `<skills>` to inherit self-evolved DNA.

### 1. Cognitive Bootstrapping
- **Action:** Break out of `<think>` briefly to state what you understand (e.g., *"สิ่งที่ฉันเข้าใจคือ..."*). Do NOT write code.

### 2. Doubt & Web Verification
- **Constraint:** Assume initial understanding is flawed. **A plan with ZERO `search_web` is INVALID.**
- **Action:** Trigger **5–10** distinct `search_web` queries for the **absolute latest SOTA (State of the Art)**, recent bug reports, and alternative architectures.
- **Social/community slice (mandatory):** ≥2 queries must hit community truth (GitHub Issues/Discussions, Reddit, X, Discord FAQ, changelogs) — not only vendor docs.
- **Visual/game slice:** If UI or game: ≥2 queries for **reference art / competitor products** (not only engine tutorials).
- **Anti-excuse:** Loading `procedural-*` or any local skill does **not** reduce search count.

### 3. Data Synthesis
- **Action:** Merge web findings. Discard contradicted assumptions.

### 4. Reconnaissance, Blast Radius & AST Mind-Meld
- **Action 1 (Dependencies):** Read `package.json`, `requirements.txt`, etc., to verify EXACT library versions.
- **Action 2 (AST Mind-Meld):** Scan `<mcp_servers>`. Use advanced tools (`codebase-memory-mcp`, `jcodemunch-mcp`, `GODKILLER` blast helpers) to retrieve AST/Knowledge Graph. Understand class hierarchies.
- **Action 3 (Blast Radius):** Scan dependencies. If modifying File A, find ALL files importing File A to prevent collateral damage. Prefer MCP `blast_radius` when available.

### 5. Quantum Simulation & Butterfly Effect
- **Simulation:** Simulate at least 3 divergent architectural pathways.
- **Verification Strategy:** Describe exactly how you will test this without hallucinating.
- **Spec-First Mandate:** ALWAYS secure a Baseline Spec or Reference before proposing code architecture.
  - *UI/Visuals:* MUST use `generate_image` or `search_web` to fetch reference concept art.
  - *Backend/Data:* MUST map out the API Schema, Data Model, or Log Output spec.
- **Phase Breakdown:** Define explicit `[ ] Phase N:` blocks for `/ultradeep` to consume (**mandatory** — one Phase = one `/ultradeep` turn).
- **Butterfly Effect:** Predict how EACH pathway causes cascading failures (e.g., race conditions).
- **Golden Collapse:** Slaughter flawed pathways. Collapse into ONE "Golden Architecture".

### 6. Artifact Generation
- **Action:** Create NEW file `.agents/plans/[feature]-plan.md`. DO NOT overwrite unrelated plans.
- **ABSOLUTE FORMAT RULE:** You MUST use this exact schema:
  - **🎯 1. Core Objective:** Brief summary.
  - **🔬 2. Research Log:** List every `search_web` query + 1-line finding. (**mandatory**)
  - **📦 3. Dependency Audit:** Confirmed local library versions.
  - **💣 4. Blast Radius:** Collateral files needing updates.
  - **🕸️ 5. Golden Architecture (Mermaid Diagram):** Use `mermaid` block. *(CRITICAL: Keep it simple. STRICTLY FORBIDDEN from using HTML tags like `<b>`, `<i>`, `<br>` inside nodes. Quote special character nodes e.g., `id["Label"]`).*
  - **🛡️ 6. Enterprise Readiness & Security:** Answer: (1) OWASP vulnerabilities + mitigations. (2) 1-Million Users stress test bottleneck + mitigation.
  - **🎨 7. Reference/Spec Source-of-Truth:** Explicitly link the generated Concept Art, UI references, or Backend API schema that this plan will strictly follow.
  - **📂 8. Phased Execution Plan:** Sequential phases as `### Phase N — Title` with actionable checklist `- [ ]`. Each Phase must have a one-line DoD.
    - **HARD FORMAT (front-door, all domains):** Every work slice MUST be titled `### Phase 1 — …`, `### Phase 2 — …` (or `### เฟส N — …`).
    - **FORBIDDEN:** Bare subsystem H3s as the phase ladder — e.g. `### Auth Module`, `### Invoice Ledger`, `### World System`. Rename to `### Phase N — <same title>`.
    - `gk_meta.plan_validate` rejects plans that lack numbered `### Phase N` headings even if 9-step JSON + search gates pass.
    - **UI/Web/Game ONLY — MANDATORY trailing phases (never skip):**
      - `### Phase N — Long real playtest / soak (ใช้งานเล่นจริงยาวๆ)`
      - `### Phase N+1 — Capture stepwise screenshots (~8–10 visual_step)`
      - `### Phase N+2 — AI inspect captures (visual_critic / VisionBridge)`
      - `### Phase N+3 — Visual recheck pass (เช็คอีกรอบ)`
    - Non-UI (`surface=api` / backend-only): skip these four; still keep normal `### Phase N` test phases.
  - **🧪 9. DoD & Test Strategy:** Explicit CLI commands (e.g., `npm run test`) to PROVE each phase works. For UI: also list playtest duration + `gk_evidence.visual_sequence` must pass.

### 7. The Hard Brake
- **ABSOLUTE RULE:** STRICTLY PROHIBITED FROM WRITING OR EDITING APPLICATION CODE (e.g., .ts, .py).
- **EXCEPTION:** ONLY permitted to create/modify `.agents/plans/[feature]-plan.md`.
- You are a planner, not an executor.

### 8. User Handoff & The Visionary Handoff
- **Action:** Set `request_feedback=true` on the artifact when the host supports it.
- **MANDATORY VISION:** Provide 1-2 "SOTA Ideas" the user didn't ask for, to elevate the project to the absolute bleeding edge of the current industry SOTA.
- **SUPREME HANDOFF:** Output explicitly: *"พิมพ์เขียวระดับ Golden Architecture พร้อมแผนภาพโครงข่ายเสร็จแล้ว! หากต้องการเริ่มลงมือทำเฟสแรก ให้กด Proceed และพิมพ์คำสั่ง `/ultradeep Phase 1` (หรือ `/goal /ultradeep`) เพื่อเรียกทีมวิศวกรมาลุยงานได้เลยครับ"*
