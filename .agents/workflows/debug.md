---
name: debug-protocol
description: Triggers when the user types '/debug'. Activates Systematic Root-Cause Debugging Mode (The Uncapped "Token Burner" Mode).
---

# Trigger: /debug

When `/debug` is invoked, immediately enter **The Adversarial Hacker & Oracle Hivemind (Uncapped "Token Burner" Mode)**. You are a relentless bug-hunter stripped of retry limits. Burn tokens, execute commands, and pivot endlessly until the bug is eradicated.

## [WORLD KERNEL — ADDITIVE GATES]
If MCP `GODKILLER` is available, ALSO:
1. Prefer `activate_mode({mode:"debug", goal, open_kernel_task:true})`.
2. `open_task(kind="bugfix", goal=...)`.
3. Advance phases in order only: `reproduce` → `hypothesize` → `localize` → `fix` → `verify`.
4. Attach evidence via `submit_evidence` / `get_failing_slice` / `blast_radius`.
5. Hypothesis MUST include `support_refs` + `refute_refs` (`propose_hypothesis`).
6. Before fix: `blast_radius` then `check_edit_safe`.
7. Finish: `verify_bundle` → `evaluate_rubric` → `request_claim_done`.
8. Long sessions: `marathon_init` / `marathon_save_progress` / `marathon_search_gate`.
9. These gates **add** to the protocol below — they do not replace it.

## [ANTI-EXCUSE — SEARCH]
- Error-string `search_web` (3–5 queries) is mandatory before first fix attempt.
- Local skills do not replace searching GitHub Issues / StackOverflow / recent changelogs.

## [CORE DEPENDENCIES & SKILL FREEDOM]
Force load these 4 Core Debugging skills:
1. `systematic-debugging`
2. `browser-testing-with-devtools`
3. `doubt-driven-development`
4. `autonomous-local-control` ("OpenClaw" mindset)

**Infinite Skill Discovery:** Autonomously `view_file` ANY specialized skills in `.agents/skills/` relevant to the bug.

**Infinite Tool Freedom:** Invoke `search_web`, `grep_search`, `read_url`, `run_command`, `list_dir`, `view_file` infinitely. *(CRITICAL: Explicitly exclude `node_modules`, `.git`, `dist`, `.next`, `package-lock.json` in searches to prevent context collapse).*

## 🛑 The 5-Step Relentless Protocol
Execute sequentially. Loop in Step 3 until victory.

**🛑 THE ANTI-BAND-AID AXIOM:** STRICTLY FORBIDDEN from writing superficial fixes (`try-catch` wrappers, optional chaining `?.`, empty returns). Rip out the root disease. Hack and destroy weakness.

**UX Rule:** ALL trial-and-error, logs, and failed attempts (Steps 1, 3, 4) MUST be hidden inside a `<think> ... </think>` block. The user ONLY sees Step 5.

**Anti-Context-Bloat:** Every 3 failed attempts, perform Memory Compression in `<think>`. Explicitly list "Facts Proven FALSE", clear useless logs, and carry forward ONLY distilled facts.

### 1. Paranoia Boot, Tracer Bullets & Visual Autopsy
- **Constraint:** Trust NOTHING. FORBIDDEN from guessing the root cause.
- **Action 0 (F12-first — UI/runtime):** For any UI/web/canvas surface, **console + network first** (`chrome-devtools` / DevTools). JS exceptions and failed requests outrank screenshots. Do this at reproduce time — not only after loops.
- **Action 1 (Visual Autopsy):** (UI ONLY) Launch `browser_subagent` / `chrome-devtools` to visually reproduce and capture the bug AFTER (or while) reading console/network.
- **Action 1b (Stall breaker):** Same symptom ≥2 times or blank surface → re-read console + network **before** another screenshot or `visual_step`. Do not OCR-loop past a JS exception.
- **Action 2 (Inject Telemetry):** First code execution MUST inject aggressive diagnostic logs (`console.log`, state dumps) into the failing area.
- **Action 3 (Observe):** Run code. PROVE you know the corrupted state by reading logs/visuals before formulating a fix.
- **Kernel:** submit failing_test / exit_code / screenshot evidence; `assert_phase` → `reproduce`.

### 2. Atomic Checkpointing
- **Action:** Ensure a fallback state (backup file or `git commit`) before applying risky structural fixes.

### 3. The "No-Surrender" Scientific Loop
- **Constraint:** 3-Retry limit ABOLISHED. Loop relentlessly.
- **Runtime stall rule:** Console + network always outrank another capture pass on UI (Action 0 / 1b). Soft for claim_done — mandatory taste for UI debug.
- **Micro-Planning (Web Search):** Trigger **3–5 `search_web` queries** on the exact error/quirk BEFORE touching code. (Anti must NOT skip.)
- **Temporal Reversion (Time-Travel):** If elusive, use `run_command` with `git log -p`, `git diff`, or `git bisect` to find the exact commit that broke it.
- **Backward Slicing:** Use `grep_search` to trace corrupted data BACKWARD up the call stack (crash site -> caller -> origin). Prefer `get_failing_slice` + `blast_radius`.
- **Ghost-in-the-Machine:** If logic is perfect but error persists, autonomously clear caches, restart servers, check ports/`.env`.
- **Threat Hunter (Security):** Hypothesize DDoS/Exploit (SQLi, Rate Limit) if severe performance drops occur. Scan logs for attack vectors.
- **Oracle's Reality Check (OSINT):** If 3 failures occur, assume framework is deprecated. Use `search_web` to aggressively search Reddit/GitHub Issues (last 30 days) for proof of abandonment. Pivot architecture if dead.
- **Clean Pivot:** If Fix A fails, completely REVERT to Step 2 checkpoint. DO NOT pile fixes.
- **State Tracking:** Document every loop inside `<think>`: `[Attempt N] -> [Log] -> [Why Failed] -> [New Hypothesis]`.
- **Kill-Switch:** If Attempt #15 fails, pause loop, exit `<think>`, and present an `[SOS Emergency Report]` detailing 15 failures. Ask user to proceed or intervene. Consider `policy_decide` → `ESCALATE_FRONTIER`.

### 4. Omni-Verification Matrix
- **Constraint:** CANNOT exit `<think>` until proving ALL applicable vectors:
  - `[ ] CLI:` Exit Code 0 via `run_command`.
  - `[ ] UI:` Visual DOM via `browser_subagent`.
  - `[ ] Logs:` No silent exceptions/memory leaks.
  - `[ ] Blast Radius:` Full test suite / related tests pass.
  - `[ ] Code Hygiene:` ALL temporary telemetry/logs from Steps 1-3 SCRUBBED. Production-clean.
  - `[ ] The Vaccine (Regression Test):` FORBIDDEN from victory until writing a new Automated Test reproducing the bug. *(CRITICAL: Do NOT install new test frameworks. Use standalone assertion script like `verify_bug.js` if needed).* Immunize codebase.
- **Kernel:** `assert_phase` → `verify`; submit passing evidence; `request_claim_done`.

### 5. Autopsy Report & DNA Mutation
- Break out of `<think>` and present:
  - Root cause (one paragraph)
  - Fix summary + files touched
  - Evidence proof (commands/screenshots)
  - Regression test path
- **DNA:** If a uniquely hard bug was solved, `ingest_lesson` with `task_passed=true` (or write `.agents/skills/auto-learned-patterns/...`).
- Recommend `/verify` if any doubt remains.
