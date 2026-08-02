# GODKILLER host write guard

Wire a **host PreToolUse hook** so native Write/Edit cannot bypass MCP.

**Policy:** GODKILLER MCP does **not** silently lock your filesystem.  
Full lock is **opt-in** on the IDE host. We ship templates; you enable them.

| Layer | What it does |
| --- | --- |
| MCP only | Gates when `gk_*` is called. Native Write still free. |
| + host write-guard | IDE asks `godkiller-write-guard` before Write/Edit. |
| + `GODKILLER_WRITE_GUARD_PROVEN=1` | Only after a live deny/allow test — then ship claims may trust the hook. |

---

## Prerequisites

```bash
pip install godkiller-mcp
# confirm CLI:
godkiller-write-guard --help
# or:
python -m godkiller_mcp.write_guard --help
```

Allowlist before coding (from MCP or CLI):

```text
gk_guard.set_paths  paths=["src/app.py","tests/test_app.py"]  workspace="."
```

Paths land in `.godkiller/write_allow.json` under the workspace / `GODKILLER_HOME`.

---

## Example: nested settings hooks

Some hosts use `~/.…/settings.json` or a project settings file:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -m godkiller_mcp.write_guard --stdin",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Exit **2** = deny (host should block the tool).

---

## Example: flat hooks JSON

Some hosts use a project or user `hooks.json`. Minimal shape also ships as:

[`src/godkiller_mcp/hooks/pretooluse_write_guard.json`](../src/godkiller_mcp/hooks/pretooluse_write_guard.json)

Point PreToolUse at `godkiller-write-guard --stdin`.

---

## Example: Antigravity-style PreToolUse (recommended full lock)

### Why this is separate from MCP

Many agent IDEs can Write via native tools without calling GODKILLER.  
`.agents/AGENTS.md` is soft law. Only a **host hook** closes that hole.

We intentionally keep MCP non-hostile: **you** turn the lock on.

### 1) Copy the template

Tracked copies:

- [`docs/templates/antigravity-write-guard.hooks.json`](templates/antigravity-write-guard.hooks.json)
- [`src/godkiller_mcp/hooks/antigravity_pretooluse_write_guard.json`](../src/godkiller_mcp/hooks/antigravity_pretooluse_write_guard.json)

```bash
# from a clone of this repo:
mkdir -p .agents/hooks
cp docs/templates/antigravity-write-guard.hooks.json .agents/hooks/godkiller-write-guard.hooks.json
```

Or paste:

```json
{
  "enabled": true,
  "PreToolUse": [
    {
      "matcher": "Write|Edit|NotebookEdit",
      "command": "godkiller-write-guard --stdin",
      "timeout": 15
    }
  ]
}
```

### 2) Merge into the host hooks config

Exact filename/UI varies by host. Goal:

- Event: **PreToolUse** (before Write/Edit)
- Matcher: `Write|Edit` (and NotebookEdit if present)
- Command: `godkiller-write-guard --stdin`  
  (or `python -m godkiller_mcp.write_guard --stdin` if the CLI is not on `PATH`)

If the IDE uses a single hooks file, **merge** the `PreToolUse` entry — do not wipe unrelated hooks.

Reload the host after saving.

### 3) Prove the hook (required before ship claims)

```bash
# Deny (expect exit 2)
echo '{"tool_name":"Write","tool_input":{"file_path":"evil.py"},"cwd":"."}' | godkiller-write-guard --stdin

# Allow after set_paths includes src/ok.py (expect exit 0)
echo '{"tool_name":"Write","tool_input":{"file_path":"src/ok.py"},"cwd":"."}' | godkiller-write-guard --stdin
```

Then in the IDE: ask the agent to Write a path **not** on the allowlist → must be blocked.

Only then set:

```text
GODKILLER_WRITE_GUARD_PROVEN=1
GODKILLER_PROFILE=ship
```

File markers / `GODKILLER_WRITE_GUARD_WIRED` alone are **not** enforcement proof.

### 4) Weaker fallback (no host hook yet)

Agent calls `gk_guard.write` / checks allowlist **before** native Write and treats deny as stop.  
This is discipline-only — same class of failure as skipping ultradeep.

### 5) Disable / uninstall full lock

MCP and write-guard are **separate switches**.

| Stop using… | Action |
| --- | --- |
| Full lock only | Remove the PreToolUse write-guard entry, or set `"enabled": false` on the hooks file · unset `GODKILLER_WRITE_GUARD_PROVEN` · reload the IDE |
| GODKILLER MCP only | Disable/remove the MCP server in host settings · soft gates go away · **write-guard still runs if left installed** |
| Everything | Detach write-guard **and** disable MCP · then native Write behaves like a normal agent IDE |

Do not assume “MCP off = lock off.” If writes still fail after disabling MCP, the write-guard hook is still attached — remove it.

---

## Threat model

- **With proven hook:** native Write gated by GODKILLER allowlist (MCP policy + host).
- **Without hook:** do **not** say “enforce”, “OS lock”, or “100% forced”. Say “MCP path only”.

---

## 30-second CLI demo

```bash
python -c "from godkiller_mcp.write_guard import persist_allow_paths; persist_allow_paths('.', ['src/ok.py'])"

echo '{"tool_name":"Write","tool_input":{"file_path":"evil.py"},"cwd":"."}' | python -m godkiller_mcp.write_guard --stdin
# → allowed:false  exit 2

echo '{"tool_name":"Write","tool_input":{"file_path":"src/ok.py"},"cwd":"."}' | python -m godkiller_mcp.write_guard --stdin
# → allowed:true   exit 0
```

Claim path (separate): open a task, skip verify → `claim_done` / exit_checklist stays `blocked`.

See also: [`HOST_VS_MCP.md`](HOST_VS_MCP.md) · [`SEAL_KEY.md`](SEAL_KEY.md) · [`SECURITY.md`](../SECURITY.md)
