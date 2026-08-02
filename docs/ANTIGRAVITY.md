# Antigravity + GODKILLER — how to use

**Audience:** Google Antigravity (and any host that reads project `.agents/`).  
**Honesty:** MCP gates `gk_*` only. Native Write stays free until you wire PreToolUse.

---

## Summary (do this)

| Step | Action |
| --- | --- |
| **1. Once on the machine** | `pip install godkiller-mcp` · add MCP server in Antigravity · set `GODKILLER_SEAL_KEY` (see [`SEAL_KEY.md`](SEAL_KEY.md)) |
| **2. Once per project** | `godkiller-bootstrap --workspace .` · reload Antigravity |
| **3. Prove (once per project / after hook change)** | Deny path not on allowlist · allow after `gk_guard.set_paths` · then optional `GODKILLER_WRITE_GUARD_PROVEN=1` |
| **4. Every task** | `/plan` → allowlist → `/ultradeep Phase N` → `/verify` → `claim_done` |

That is the whole product loop.

---

## 1) Install MCP (machine, once)

```bash
pip install godkiller-mcp
python -c "import secrets; print(secrets.token_hex(32))"
```

Antigravity MCP config (example — use **your** project paths, never commit real keys):

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp",
      "env": {
        "GODKILLER_PROFILE": "ship",
        "GODKILLER_WORKSPACE": "/absolute/path/to/your/project",
        "GODKILLER_HOME": "/absolute/path/to/your/project/.godkiller-session",
        "GODKILLER_SEAL_KEY": "REPLACE_WITH_64_HEX",
        "GODKILLER_SEAL_REQUIRE_ENV": "1"
      }
    }
  }
}
```

Confirm: call `gk_meta.status` in a chat. If it fails, stop — the kernel is not up.

---

## 2) Bootstrap each project (repeatable)

From the **project root** (the folder you open in Antigravity):

```bash
godkiller-bootstrap --workspace .
```

Creates / updates:

| File | Commit? |
| --- | --- |
| `.agents/AGENTS.md` | Yes (constitution) |
| `.agents/hooks.json` | Yes (portable PreToolUse) |
| `.agents/hooks/godkiller-write-guard.cmd` or `.sh` | Yes |
| `.agents/hooks/godkiller-write-guard.local.cmd` / `.local.sh` | **No** — machine Python pin, gitignored |
| `.agents/hooks/.gitignore` | Yes (ignores the local pin) |

Reload Antigravity on that workspace after bootstrap.

**If Write-guard suddenly does nothing** (Python moved, new venv, CLI missing): run `godkiller-bootstrap --workspace .` again. It refreshes the local pin without putting personal paths into the portable wrapper.

---

## 3) Prove the lock (before claiming “full lock”)

```bash
# Deny → expect exit 2
echo '{"tool_name":"Write","tool_input":{"file_path":"evil.py"},"cwd":"."}' | godkiller-write-guard --stdin

# Allowlist, then allow → expect exit 0
python -c "from godkiller_mcp.write_guard import persist_allow_paths; persist_allow_paths('.', ['src/ok.py'])"
echo '{"tool_name":"Write","tool_input":{"file_path":"src/ok.py"},"cwd":"."}' | godkiller-write-guard --stdin
```

In the IDE: ask the agent to Write a path **not** on the allowlist → must be blocked.

Only then set in MCP env:

```text
GODKILLER_WRITE_GUARD_PROVEN=1
```

Details: [`WRITE_GUARD_HOOKS.md`](WRITE_GUARD_HOOKS.md)

---

## 4) Everyday workflow (every feature)

1. **Open the project** in Antigravity (MCP already on at host level — do not reinstall per folder).
2. **`/plan`** — Mermaid + `### Phase N` only. No app code in plan mode.
3. **Allowlist** — `gk_guard.set_paths` for the files this Phase may touch.
4. **`/ultradeep Phase N`** — one Phase per turn.
5. **`/verify`** → disk proof → `claim_done`. Chat “done” does not open the gate.

Soft law lives in `.agents/AGENTS.md`. Hard write lock is PreToolUse → write-guard.

---

## 5) New project checklist

```text
[ ] pip / MCP already installed on this machine
[ ] cd your-new-repo
[ ] godkiller-bootstrap --workspace .
[ ] Point GODKILLER_WORKSPACE / GODKILLER_HOME at this project (or per-session home)
[ ] Reload Antigravity
[ ] Prove deny/allow (section 3)
[ ] Start with /plan
```

---

## 6) Turn things off

| Want | Do |
| --- | --- |
| Normal IDE writes again | Remove Write\|Edit PreToolUse from `.agents/hooks.json` · unset `WRITE_GUARD_PROVEN` · reload |
| MCP off only | Disable the godkiller MCP server · **hook still runs if left in hooks.json** |
| Everything off | Detach hook **and** disable MCP |

---

## Intensity (honest)

| You installed | What you get |
| --- | --- |
| MCP only | Judge on `gk_*`. Native Write free. |
| + `AGENTS.md` | Soft standing orders. Agent can skip. |
| + bootstrap / PreToolUse | Native Write/Edit gated by allowlist. |
| + `WRITE_GUARD_PROVEN=1` | Ship posture may trust the hook — only after live prove. |

See also: [`HOST_VS_MCP.md`](HOST_VS_MCP.md) · [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md) · [`SEAL_KEY.md`](SEAL_KEY.md)
