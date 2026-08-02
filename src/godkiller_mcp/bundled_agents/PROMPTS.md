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
After the plan is accepted, run /ultradeep Phase 1.
Before editing files, call gk_guard.set_paths for paths in that Phase.
Finish with /verify then claim_done — do not declare done from chat alone.
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
