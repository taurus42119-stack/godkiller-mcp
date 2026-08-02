# Why Antigravity can edit files without GODKILLER

```text
┌─────────────────────────┐
│  Antigravity / IDE host │
│  Write / Edit / Terminal│  ← native tools (NOT MCP)
└───────────┬─────────────┘
            │ agent may use these freely
            ▼
┌─────────────────────────┐
│  Workspace files on disk│
└───────────┬─────────────┘
            │ only if agent CHOOSES to call MCP
            ▼
┌─────────────────────────┐
│  godkiller-mcp          │
│  edit_safe / verify /   │
│  claim_done / probe     │  ← gates live HERE
└─────────────────────────┘
```

MCP is a **toolbox the model may call**, not a kernel that wraps every IDE write.
So: plan lock / claim_done / freshness only fire on GODKILLER tool calls.

To close the hole you need at least one of:

1. **Host PreToolUse hook** — `python -m godkiller_mcp.write_guard --stdin` (see `docs/WRITE_GUARD_HOOKS.md`); allowlist via `gk_guard.set_paths` / swarm collect  
2. **`python -m godkiller_mcp.prove`** — human/CI re-proves the tree *outside* the agent’s story  
3. **Discipline** — workflow that forbids native write (weak; agents skip it)

Freshness + prove + **ship profile** are how we stop “I already tested” after a silent native edit.
`GODKILLER_PROFILE=ship` → `DEV_RELAX` cannot disarm armor.
Without ship profile: `GODKILLER_FAULT_PROBE=0` / `FRESHNESS=0` only work under `GODKILLER_DEV_RELAX=1`.

**MCP alone does not intercept native Write.** Product shape that works: MCP = policy brain (`gk_guard` / swarm paths) + host hook = enforcement.

## Intensity (one paragraph)

Claim/search/evidence gates are **harsh on the MCP path**. Native Write is **weak** until PreToolUse → `godkiller-write-guard` is live and `GODKILLER_WRITE_GUARD_PROVEN=1`. Do not sell “OS lock” or “always exhaustive search.” See README *Intensity layers (honest)*.

**Ship checklist (host):** `GODKILLER_PROFILE=ship` · pin `GODKILLER_WORKSPACE` · distinct `GODKILLER_HOME` per concurrent session · `GODKILLER_SEAL_KEY` · wire PreToolUse → prove → only then `GODKILLER_WRITE_GUARD_PROVEN=1`. Empty PROFILE still keeps armor on (`ship_mode()`), but is not the same as declaring the ship deployment posture above.

**PROFILE=ship claim gate:** `claim_done` / `exit_checklist` block on `write_guard` until `GODKILLER_WRITE_GUARD_PROVEN=1`. That still does **not** intercept native Write by itself — it refuses a ship “done” claim until you attest the host hook. Bypass: leave PROFILE unset for experiments, or `GODKILLER_REQUIRE_WRITE_GUARD_PROVEN=0` (not for ship).

**Smarter defaults (ROI):** bugfix `edit_safe` requires search+blast first; `plan_template` injects fail lessons; `gk_code.read_all` needs symbol digest (jcodemunch / map / search) before dump.

