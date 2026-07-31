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
