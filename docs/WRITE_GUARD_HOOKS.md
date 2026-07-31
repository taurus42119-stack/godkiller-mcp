# GODKILLER host write guard — Claude Code / Cursor-style PreToolUse

Wire this so **native Write/Edit** cannot bypass MCP plan envelope.

## Claude Code (`~/.claude/settings.json` or project `.claude/settings.json`)

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

The CLI reads hook JSON on stdin and exits **2** on deny (Claude Code block).

Before coding, set allowlist from MCP:

```text
gk_guard.set_paths  paths=["src/app.py","tests/test_app.py"]  workspace="."
# or after swarm.collect — paths are written to .godkiller/write_allow.json
```

## Antigravity

If the IDE exposes PreToolUse / equivalent: point it at the same command.  
If not yet: use `gk_guard.write` from the agent **before** native writes, and treat deny as hard stop — weaker than a host hook.

## Threat model

- With hook: native Write is gated by GODKILLER allowlist (MCP + host).
- Without hook: MCP gates still apply only when tools are called — **do not say “enforce”**.

## 30-second demo

```bash
# 1) Allow only one path
python -c "from godkiller_mcp.write_guard import persist_allow_paths; persist_allow_paths('.', ['src/ok.py'])"

# 2) Hook-style deny (exit 2)
echo '{"tool_name":"Write","tool_input":{"file_path":"evil.py"},"cwd":"."}' | python -m godkiller_mcp.write_guard --stdin
# → allowed:false  exit code 2

# 3) Allow listed path
echo '{"tool_name":"Write","tool_input":{"file_path":"src/ok.py"},"cwd":"."}' | python -m godkiller_mcp.write_guard --stdin
# → allowed:true   exit code 0
```

Claim path (separate): open a task, skip verify → `claim_done` / exit_checklist stays `blocked`.
