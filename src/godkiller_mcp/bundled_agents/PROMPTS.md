# GODKILLER — copy-paste prompts

Paste these in the IDE chat. Do not invent a longer ritual.

---

## Autopilot (normal use — this is enough)

```text
/goal /ultradeep
```

Meaning (agent must already know from protocol — you should not re-explain every turn):

1. `gk_mode.activate` ultradeep · one Phase only this turn
2. When Phase DoD is done: `gk_guard.end_turn` · `marathon_save_progress` · `marathon_next_wake`
3. Call host **`schedule`** (~5s) with that wake prompt · **STOP** · do not ask the user
4. On wake: next Phase only · repeat until plan done · then `/verify` → `claim_done`

`schedule` is an **Antigravity host** tool. GODKILLER only supplies the wake prompt (`marathon_next_wake`).

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

## Start work (manual / first Phase only)

```text
First: gk_mode.activate mode=plan with the goal.
/plan — write only under .agents/plans/. No app code.
Then: /goal /ultradeep
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

| When | What you type |
| --- | --- |
| New folder | **New project** above |
| Keep building | `/goal /ultradeep` |
| Hook broken | **Hook broken** above |
