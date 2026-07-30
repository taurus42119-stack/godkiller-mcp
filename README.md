# GODKILLER MCP

**The Antigravity phase kernel** — an MCP built for Google Antigravity agents that skip planning, rush multi-file edits, and claim “done” without proof on disk.

Other MCPs help agents *read code* or *drive a browser*. GODKILLER makes the agent **obey an engineering process**: search → plan → phase gates → per-file think/plan/edit → verify → only then `claim_done`.

[![PyPI](https://img.shields.io/pypi/v/godkiller-mcp.svg)](https://pypi.org/project/godkiller-mcp/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-success.svg)](tests/)

⭐ If this upgrades your Antigravity / Cursor agent workflow, a GitHub star helps a lot.

**Contact:** [Facebook — Pronphorm Pakdee](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee) · [Instagram @Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Why this exists (the real pitch)

Google **Antigravity** is powerful — and often **refuses to split work into phases**. Typical failure modes:

- Jumps straight into code with no `/plan`
- Edits many files in one rush
- Says “fixed” without running tests on disk
- Loses intent across long sessions
- Skips web/search because local skills “already know enough”

**Almost nobody ships an MCP whose main product is fixing that.** Code-intel and browser MCPs are common. A **governance kernel for Antigravity** is not.

GODKILLER was designed for that gap first. Code search, Semgrep, Playwright, and memory graph grew around the kernel — they are force multipliers, not the headline.

```text
User goal
  → /ask | /plan | /debug | /ultradeep | /verify
  → open task + evidence store
  → forced search / 9-step plan (when required)
  → edit only when gates pass
  → verify_bundle (pytest / commands) on disk
  → request_claim_done  (blocked if evidence missing)
```

---

## What you get

| Layer | What it enforces |
| --- | --- |
| **Phase machine** | `assert_phase` / `claim_done` — illegal skips blocked |
| **Plan OS** | 9-step blueprint validate before fix-phase edits |
| **Edit safety** | blast radius + `check_edit_safe` before mutation |
| **/ultradeep** | One plan phase per turn (marathon) **and** think → plan → edit **one file at a time** |
| **Verify** | Live commands on disk — text-only “done” is not enough |
| **Memory graph** | Task → phase → evidence → lesson (workflow memory, not just source index) |
| **Extras** | `gk_code` / `gk_scan` / `gk_browser` when you need depth |

### `/ultradeep` per-file loop (additive)

Continuous work is fine — batch rush is not:

1. Queue files → `ultradeep_queue`  
2. Deep think (≥3 hypotheses) → `ultradeep_think`  
3. Per-file plan → `ultradeep_plan`  
4. `check_edit_safe` with **one path** → edit → verify  
5. `ultradeep_advance` → next file  

Marathon “one Phase per turn” still applies. Opt out of per-file gate with `per_file_gate=false` if you need legacy behavior.

---

## Install

```bash
pip install godkiller-mcp
# optional:
#   pip install 'godkiller-mcp[browser]' && playwright install chromium
#   pip install 'godkiller-mcp[scrape]'
```

From source:

```bash
git clone https://github.com/taurus42119-stack/godkiller-mcp.git
cd godkiller-mcp
pip install -e ".[all]"
pytest -q
```

### MCP config (Antigravity / Cursor / Claude Desktop)

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp"
    }
  }
}
```

Alternative:

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "python",
      "args": ["-m", "godkiller_mcp.server"]
    }
  }
}
```

Optional: set `GODKILLER_TOOLS_DIR` if helpers (`rg`, `fd`, `semgrep`, `ast-grep`) are not on `PATH`.

---

## Slim tool surface (12 facades)

Legacy handlers still live under the hood; agents see a short list with `action=`:

| Tool | Role |
| --- | --- |
| `gk_route` | Classify intent → `/ask` `/plan` `/debug` `/ultradeep` `/verify` |
| `gk_mode` | Activate protocols, skills catalog, **ultradeep file gate** |
| `gk_task` | open, hypothesize, blast_radius, edit_safe, failing_slice |
| `gk_phase` | assert, claim_done, rubric |
| `gk_evidence` | submit, capture_shot, visual_critic, journeys |
| `gk_verify` | bundle (pytest), soak, loop_*, competitor, ladder |
| `gk_memory` | lessons, marathon, query_graph, what_blocked |
| `gk_code` | map, search, read_full, ast_grep, council, … |
| `gk_scan` | AST/CWE heuristics + optional Semgrep |
| `gk_browser` | Playwright navigate / snapshot / screenshot / click / fill |
| `gk_handoff` | write_spec / write_feedback gates |
| `gk_meta` | plan_template / plan_validate (9-step) |

---

## Modes

| Mode | Job |
| --- | --- |
| `/ask` | Explore & interview — no application code edits |
| `/plan` | Spec + research — 9-step plan before build |
| `/debug` | Reproduce + hypothesize before fix |
| `/ultradeep` | Supreme orchestrator: marathon + max tool swarm + per-file gate |
| `/verify` | Empirical proof, then claim_done |

Protocols load from project `.agents/workflows/` when present; the package also ships a bundled `/ultradeep` fallback so activate_mode still works without copying the full tree.

---

## vs Cursor peer MCPs

| Peer | Strength | GODKILLER edge |
| --- | --- | --- |
| **jcodemunch** | Code structure / intel | **Process:** phase + plan + claim gates Antigravity cannot shrug off |
| **codebase-memory** | Source graph memory | **Workflow graph:** task → phase → evidence → lesson |
| **chrome-devtools** | Full CDP browser | Orchestrates evidence + verify; optional Playwright when peer isn’t loaded |

Use peers **with** GODKILLER when you want: GODKILLER = governor, peers = sensors.

Harness notes: [`benchmarks/cursor_peers/`](benchmarks/cursor_peers/)  
Arena lab artifacts: [`benchmarks/arena_logs/`](benchmarks/arena_logs/)

---

## Lab note (honest)

Isolated arena evaluations (same model, with vs without MCP) and logs live under `benchmarks/`. Treat them as **lab evidence for the governance thesis**, not a claim that every repo in the world is solved. Unit tests in `tests/` cover facades, plan OS, file gate, secrets isolation, and path hygiene:

```bash
pytest -q
```

---

## Security (short)

- Secrets via scope-safe loader — key names only over MCP, values stay local  
- Verify/soak prefer safer process exec (`shell=False` where possible)  
- Optional scrape/browser are explicit tools, not silent phone-home  

---

## License

MIT © 2026 GODKILLER Team — see [LICENSE](LICENSE)
