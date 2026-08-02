# GODKILLER — copy-paste prompts

Paste these in the IDE chat. Do not invent a longer ritual.

---

## New project (first time in this folder)

```text
This project is not wired for GODKILLER yet.
Run: python -m godkiller_mcp.bootstrap --workspace .
Do not commit godkiller-write-guard.local.cmd
When done, tell me to reload the IDE.
Do not write application code yet.
```

After reload (optional — only if you want Write lock proven):

```text
Prove write-guard: deny a path outside the allowlist; allow after set_paths.
Do not build features yet.
```

---

## Start work (every feature)

```text
/plan
Build: <describe what you want>
After the plan is accepted, run /ultradeep Phase 1 ONLY.
Before edits: gk_guard.set_paths for Phase 1 files only (ship default: 1 path).
Do not touch Phase 2/3 in this turn.
When Phase 1 is done: gk_guard.end_turn, then stop / schedule wake.
Finish later Phases the same way. /verify then claim_done — never declare done from chat alone.
```

---

## Hook broken / Python moved

```text
Run python -m godkiller_mcp.bootstrap --workspace . again.
Do not commit godkiller-write-guard.local.cmd
When done, tell me to reload the IDE.
Do not write application code yet.
```

---

## Cheat sheet

| When | Prompt block |
| --- | --- |
| New folder | **New project** above |
| Normal coding | **Start work** above |
| Write not blocked | **Hook broken** above |
