# Agent protocol

When the host lists a **godkiller** MCP server:

1. First call `gk_meta.status`. If it fails, stop.
2. Before edits: `gk_task` / `gk_phase`. Native Write alone is a protocol miss on WITH arms.
3. Bugfix: search evidence → `blast_radius` → `edit_safe`.
4. Before dump-all: symbol digest / `gk_code.map` / `search` with `task_id`.
5. Before done: `gk_verify.exit` → `directive: pass` → `gk_phase.claim_done`.
6. State must land under `.godkiller/` or `GODKILLER_HOME`.
7. Do not invent tool names, scores, or GREEN.

```text
goal → mode → plan → search/blast → edit → verify → hollow → probe → exit → claim_done|blocked
```
