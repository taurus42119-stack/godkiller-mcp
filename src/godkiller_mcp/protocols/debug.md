# /debug — Self-CTF *signal* loop (NOT a real debugger)

Honest mouth: this is **self_ctf_signal** — SecurityScan + token/heuristic search
on **THIS workspace only**. It does **not** find real bugs the way a debugger or
pytest oracle does. Do not claim “debug found the root cause” from CTF ticks alone.

Reproduce. Attack your own code. Do not touch the open internet.

## Hard rules

1. Target = workspace / allowed localhost only. **Forbidden:** hunting real orgs, public CTF against third parties, “search the web then exploit”.
2. No fix before: reproduce evidence **or** Self-CTF findings on disk.
3. Loop: `debug_self_ctf_start` → `debug_self_ctf_tick` / `debug_self_ctf_run_until` until findings (or max_rounds). Server forces continue when empty. Findings are **signals**, not proof — verify with tests / `fault_probe` / evidence.
4. Then: hypothesis → localize (`blast_radius`) → `check_edit_safe` → fix → `verify_bundle`.
5. Claim blocked without failing→passing proof.
6. **Posture:** pessimistic + win USER goal. Capability doubt → `tool_propose` (5–10) → approve/reject_all → `tool_used` if approved. Never silent install.
7. **UI/runtime (priority #1 for UI):** console + network via `chrome-devtools` / DevTools **before** screenshot theater or `visual_step` loops. Soft for claim_done — hard for good taste when debugging UI.

## Tools

- `debug_self_ctf_start(workspace, goal, max_rounds?)`
- `debug_self_ctf_tick(task_id)` — one adversarial round (scan + search), workspace-scoped
- `debug_self_ctf_run_until(task_id, fault_probe?)` — tick until findings / max_rounds; optional fault_probe on hit paths
- `tool_propose` / `tool_approve` / `tool_reject_all` / `tool_used` — search≠install
- Classic: failing slice, blast_radius, verify_bundle, repair_wake if verify fails

## Unlike Anthropic eval failure

They thought simulation + had live net. We **refuse** open-net attack surface; agency stays inside the repo under test.
