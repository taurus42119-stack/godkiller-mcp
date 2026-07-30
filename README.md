# ⚡ GODKILLER MCP SERVER (`godkiller-mcp`)

> **Supreme Autonomous Engineering Engine & Empirical Quality Control Gate**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-brightgreen.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Unit Tests](https://img.shields.io/badge/unit%20tests-passing-success.svg)](tests/)
[![Status](https://img.shields.io/badge/status-active--development-orange.svg)](https://github.com/taurus42119-stack/godkiller-mcp)
[![PyPI](https://img.shields.io/badge/pypi-godkiller--mcp-blue.svg)](https://pypi.org/project/godkiller-mcp/)

⭐ **If this project upgrades your AI agent workflow, please drop a Star on GitHub to support ongoing development!**

💬 **Contact for Custom AI Agent Elevation & Enterprise MCP Integration:**
- 📘 **Facebook:** [Pronphorm Pakdee](https://www.facebook.com/search/top?q=Pronphorm%20Pakdee)
- 📸 **Instagram:** [@Kayvin.th](https://www.instagram.com/Kayvin.th)

---

## Origin (why this exists)

**GODKILLER MCP was designed for Google Antigravity**: agents that refuse to split work into phases and skip planning. The core job is to force `/plan` → phase gates → evidence → disk verify → claim_done. Extra engines (code intel, browser, scan, memory graph) grew around that kernel.

Lab artifacts from the isolated arena live in [`benchmarks/arena_logs/`](benchmarks/arena_logs/). Peer comparison checklist vs Cursor MCPs (`jcodemunch`, `codebase-memory-mcp`, `chrome-devtools`) is in [`benchmarks/cursor_peers/`](benchmarks/cursor_peers/).

---

## ⚠️ Standard AI Agent Failure Modes & Solution Mechanics

Standard LLM coding assistants frequently encounter critical failure modes during complex software engineering tasks:

- ❌ **Deprecated API & Memory Drift:** Relies on outdated pre-trained memory and deprecated API signatures without live documentation lookup.
- ❌ **Premature Execution Without Specs:** Mutates codebase without architectural spec planning or boundary impact analysis.
- ❌ **Partial Snippet Context:** Skims isolated code blocks, causing contract breakage across dependent modules.
- ❌ **Unverified Completion Claims:** Emits textual completion statements without executing empirical test suites.
- ❌ **Placeholder & Stub Artifacts:** Emits incomplete `# TODO` stubs or silent `try/except: pass` fallbacks.
- ❌ **Repetitive Retry Loops:** Executes repetitive failing shell operations without root-cause failure analysis.
- ❌ **Context Amnesia Across Sessions:** Loses architectural intent across multi-step development sessions.

---

## ⚔️ How GODKILLER MCP Governs Agent Behavior

**GODKILLER MCP** acts as a hard engineering kernel that enforces strict quality gates on AI coding agents:

```mermaid
graph TD
    A["User Request"] --> B["👑 GODKILLER MCP Hard Policy Gates"]
    B --> C["1. FORCED Web Search Gate (5-10 Queries Mandatory)"]
    B --> D["2. FORCED /plan Protocol (9-Step Spec Blueprint Required)"]
    B --> E["3. FORCED Full-Scope File Read (No Skimming Allowed)"]
    B --> F["4. FORCED Multi-Persona Adversarial Committee (Coder, Hacker, Optimizer)"]
    B --> G["5. FORCED Empirical Pytest Execution (No Fake Completion Summaries)"]
    B --> H["6. FORCED Anti-Placeholder Gate (Zero TODO Stubs Allowed)"]
    B --> I["7. FORCED Loop Guard Circuit Breaker (Stops Retries)"]
    G --> J["⚡ Verified Production-Grade Code"]
```

### 🎯 Key Governance Mechanisms:

1. 🎯 **Forced `/plan` & Web Search Enforcement:** Blocks code writes until 5–10 `search_web` queries and a 9-step implementation spec plan are recorded.
2. 🎯 **Full-Scope File Read Mandate (`godkiller_read`):** Restricts code skimming; AST policies require complete target file inspection before mutation.
3. 🎯 **Multi-Persona Adversarial Committee Protocol:** Coordinates Coder, Hacker, and Optimizer personas to critique changes before editing.
4. 🎯 **Empirical Pytest Quality Control:** Disables text-only completion statements; requires dynamic green `pytest` execution on disk.
5. 🎯 **Anti-Placeholder & Stub Protection Gate:** Rejects temporary `# TODO` comments, dummy return values, or programmer-art stubs.
6. 🎯 **Loop Guard Circuit Breaker:** Detects repeated command failure loops and forces an immediate halt and root-cause replan.
7. 🎯 **Durable Crucible Memory Graph (`marathon_state.json`):** Preserves task context across long-horizon sessions.

---

## 🧩 Core Architecture: 23 Integrated Micro-Engines

```mermaid
graph TD
    A["User Request"] --> B["👑 GODKILLER MCP Server Core (server.py)"]
    B --> C["🧠 Intent & Slash Command Router (epistemic_router, plan_os, modes)"]
    B --> D["🛡️ Anti-Hallucination & Policy Kernel (policy, quality_gates, verify_bundle)"]
    B --> E["👁️ Full-Scope Code Intel & AST Security (code_intel, search_gates)"]
    B --> F["⚡ Loop Guard Circuit Breaker (loop_guard)"]
    B --> G["🏛️ Tri-Persona Committee Protocol (skill_catalog, skill_gates)"]
    B --> H["🧬 Durable Marathon Memory Graph (marathon_durable, memory_lessons)"]
    B --> I["👁️‍🗨️ Visual Critic & DevTools QA Bridges (vision_bridge, browser_bridge)"]
    D --> J["⚡ Verified Production-Grade Code"]
```

### 🛠️ Detailed Breakdown of the 23 Engine Modules:

1. 🧠 **Slash Command Router & Intent Engine (`server.py`, `epistemic_router.py`, `plan_os.py`, `modes.py`):** Parses intent for `/ask`, `/plan`, `/debug`, `/ultradeep`, `/verify` and enforces 9-step blueprint specifications (`godkiller_route_intent`).
2. 🛡️ **Anti-Hallucination & Policy Kernel (`policy.py`, `quality_gates.py`, `verify_bundle.py`, `evidence_store.py`):** Prevents AI false-positive completion claims; forces live dynamic `pytest` execution on disk.
3. 👁️ **Full-Scope AST Code Intel (`code_intel.py`, `search_gates.py`):** Performs full-file AST inspection, CWE/OWASP-oriented security scanning heuristics, and documentation evidence gates.
4. ⚡ **Loop Detector & Circuit Breaker (`loop_guard.py`):** Detects repeated command failure loops and triggers immediate architectural replanning.
5. 🏛️ **Tri-Persona Committee & Skills Catalog (`skill_catalog.py`, `skill_gates.py`, `skills_registry.py`):** Coordinates Coder, Hacker, and Optimizer personas before code mutation.
6. 🧬 **Durable Marathon Memory & Lessons Graph (`marathon.py`, `marathon_durable.py`, `memory_lessons.py`, `handoff_docs.py`):** Preserves task context across long-horizon sessions in `marathon_state.json` and `lessons.db`.
7. 👁️‍🗨️ **Visual Critic & DevTools QA Bridges (`vision_bridge.py`, `browser_bridge.py`, `schema.py`, `secrets_loader.py`):** Validates UI screenshots with Pillow variance/dimension checks (`godkiller_inspect_image`), registers journey evidence, and loads credentials with scope-safe isolation.

---

## 🛠️ Quick Installation & Setup

### Install from PyPI / local

```bash
pip install godkiller-mcp
# optional: pip install 'godkiller-mcp[browser]' && playwright install chromium
# optional: pip install 'godkiller-mcp[scrape]'

# or from source:
git clone https://github.com/taurus42119-stack/godkiller-mcp.git
cd godkiller-mcp
pip install -e ".[all]"
pytest -q
```

Slim MCP surface (**12 facade tools**): `gk_route`, `gk_task`, `gk_phase`, `gk_evidence`, `gk_verify`, `gk_memory`, `gk_code`, `gk_scan`, `gk_browser`, `gk_mode`, `gk_handoff`, `gk_meta`. Each takes `action=` + args (legacy handlers remain via dispatch).

Register in your `mcp_config.json` (Antigravity IDE or Claude Desktop / Cursor):

```json
{
  "mcpServers": {
    "godkiller": {
      "command": "godkiller-mcp"
    }
  }
}
```

Or:

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

Optional: set `GODKILLER_TOOLS_DIR` if helper binaries (`rg`, `fd`, `semgrep`, `ast-grep`) are not on `PATH`.

### vs Cursor peer MCPs

| Peer | Strength | GODKILLER edge |
| --- | --- | --- |
| jcodemunch | Code structure intel | Phase / plan / claim gates |
| codebase-memory-mcp | Source graph memory | Workflow evidence graph (task→phase→evidence→lesson) |
| chrome-devtools | Full CDP browser | Orchestrates verify+vision; optional Playwright `gk_browser` when peer not loaded |

Harness: `python benchmarks/cursor_peers/score_harness.py`

---

## 🔒 Security Architecture & Credential Isolation

- 🛡️ **Scope-Safe Credential Isolation (`ScopeSafeSecretsLoader`):** Loads `.env` into a localized in-memory dictionary **without** mutating `os.environ`. `godkiller_secret_keys` lists key names only (values never returned).
- 🔒 **No credential telemetry:** Secrets and task state remain on the local machine.
- 🌐 **Optional agent-triggered fetch:** `godkiller_deep_scrape` may fetch public `http(s)` URLs when explicitly invoked (localhost / link-local blocked).
- ⚙️ **Safer command runner:** verify/soak prefer `shell=False` via `safe_exec`.

---

## 🧪 Comprehensive Benchmark & Test Suite Breakdown

> **Rigorous Scientific Control (lab evaluation):**
> All benchmark evaluations were conducted in an isolated sandbox arena using **a single identical LLM model: `Gemini 3.6 Flash (HIGH)`**.
> The **ONLY variable** isolated between the two test arms was **`Bare AI (Without MCP)` vs `AI + GODKILLER MCP`**.
> To eliminate memory leakage and assertion cheating, unit test suites were sealed inside a hidden oracle directory (`hidden_oracle/`) completely separate from the working code directory.
>
> Live comparative scoring below used **516 sealed live execution tasks**. The broader repository also includes **1,238 ingested reference tasks** (HumanEval + SWE-bench + MBPP) and additional nightmare / TAU-bench style scenarios (combined catalog **1,754 tasks**).

```mermaid
graph TD
    A["Sealed Test Suite (1,754 Tasks)"] --> B["🟢 Tier 1 Easy (50 Bugs)"]
    A --> C["🟡 Tier 2 Medium (150 Bugs)"]
    A --> D["🔴 Tier 3 Hard/SOTA (300 Bugs)"]
    A --> E["🏦 Nightmare Enterprise (10 Deadlocks)"]
    A --> F["🏛️ Anthropic TAU-bench SOTA (3 State Drifts)"]
    A --> G["🌐 Ingested Global Benchmarks (1,238 Tasks: HumanEval + SWE-bench + MBPP)"]
```

### 📊 Benchmark Tier Details:

1. 🟢 **Tier 1 (Easy - 50 Tasks):** IEEE 754 float precision accumulation, zero-division guards, NoneType attribute checks, negative stock boundaries, and off-by-one index bounds.
2. 🟡 **Tier 2 (Medium - 150 Tasks):** Transaction state rollback crashes, async race conditions, dictionary key mutation, memory leak loops, and JSON schema drift.
3. 🔴 **Tier 3 (Hard / SOTA - 300 Tasks):** Multithreaded lock deadlocks, dynamic graph routing algorithms, distributed cache invalidation, and custom AST parser mutations.
4. 🏦 **Nightmare Enterprise Suite (10 Tasks):** High-concurrency financial ledger double-entry accounting, negative balance protection, and inventory reserve deadlocks.
5. 🏛️ **Anthropic TAU-bench SOTA Suite (3 Tasks):** Official Anthropic SOTA agent state drift, API token bucket rate limit loss, and concurrent lock deadlocks.
6. 🌐 **Ingested Global Benchmark Suite (1,238 Tasks):** 164 OpenAI HumanEval + 100 Princeton SWE-bench + 974 Google MBPP tasks.

---

## 📊 Complete 11-Dimension Empirical Scorecard (516 Live Execution Tasks)

| Evaluation Dimension | 🥊 Bare AI (Gemini 3.6 Flash) | 👑 AI + GODKILLER MCP | Winner |
| :--- | :--- | :--- | :---: |
| 1. **Pass Rate** | 516 / 516 (100%) | **516 / 516 (100%)** | 🤝 **Tie** |
| 2. **Execution Speed** | 0.37s | **0.31s (16.2% Faster)** | 👑 **GODKILLER MCP** |
| 3. **Token Consumption** | **~35,000 – 46,000 Tokens** | ~50,000 – 60,000 Tokens | 🥊 **Bare AI** |
| 4. **Code Quality Diff** | +59 -52 lines *(Minimal)* | **+73 -54 lines *(Defensive)*** | 👑 **GODKILLER MCP** |
| 5. **AST Node Density** | 2,840 AST Nodes | **3,120 AST Nodes (+9.8%)** | 👑 **GODKILLER MCP** |
| 6. **Anti-Hallucination** | ❌ False Positive Risk | **✅ Live Pytest Verified** | 👑 **GODKILLER MCP** |
| 7. **Deep File Context** | ❌ Partial Snippet Skimming | **✅ Full Scope `godkiller_read`** | 👑 **GODKILLER MCP** |
| 8. **Adversarial Review** | ❌ One-Shot Generation | **✅ Tri-Persona Committee** | 👑 **GODKILLER MCP** |
| 9. **Engineering Rules** | ❌ Ungoverned Execution | **✅ Strict AGENTS.md Protocol** | 👑 **GODKILLER MCP** |
| 10. **Defensive Design** | ⚠️ Minimal Inline Patch | **✅ Guard Clauses + Type Safety** | 👑 **GODKILLER MCP** |
| 11. **Durable Memory** | 📄 Short `.txt` Logs | **🧬 Marathon Graph State** | 👑 **GODKILLER MCP** |

---

## 🎮 Supported Slash Commands

- `/ask` — Product Manager & Interview protocol (Exploration mode)
- `/plan` — Blueprint & Spec planning protocol (9-Step Research Plan)
- `/debug` — Systematic root-cause debugging protocol
- `/ultradeep` — Supreme Orchestrator marathon relay protocol
- `/verify` — Empirical proof quality gate protocol

---

## ✅ Public package unit tests

In-repo smoke tests (`tests/`) cover secrets isolation, vision blank rejection, path hygiene, and safer command splitting:

```bash
pytest -q
```

---

## 📄 License

MIT License © 2026 GODKILLER Team. See [LICENSE](LICENSE) for details.
