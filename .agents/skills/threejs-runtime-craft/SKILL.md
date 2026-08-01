---
name: threejs-runtime-craft
description: >-
  Three.js / WebGL / browser 3D: local three.js mirror routing, version match,
  and when threejs-devtools-mcp / chrome-devtools help. Useful whenever a task
  involves Three.js, WebGL, R3F, CSM/shadows, or in-browser 3D scenes/models.
---

# Three.js Runtime Craft

Load when the work touches Three.js, WebGL, R3F, browser 3D games, or in-engine 3D models.

Pair with: `game-development`, `game-ready-3d-pipeline` (meshes), Rule 8 (console+network before screenshot theater).  
Supreme law still wins: search + evidence + claim gates.

## Available tooling (consider by task — no extra user order needed)

These may already be on the host. **You decide** whether this turn needs them:

| Tooling | Good fit |
|---|---|
| **`threejs-devtools-mcp`** | Running Three/WebGL app — inspect scene graph, materials, lights, shadows, perf |
| **`chrome-devtools` / DevTools** | Console + network (Rule 8 priority for any UI/runtime) |
| **`@modelcontextprotocol/server-threejs`** | Docs (`learn_threejs`) or sandbox preview — optional |

If a needed MCP is listed in constitution but not connected: `gk_mode.tool_propose` (or host equivalent). Do not invent tool results.

GODKILLER still owns claim/evidence — a clean threejs-devtools inspect does not replace `claim_done` gates.

## Local mirror (official source — copy-study)

Put a local clone of three.js anywhere, then point study reads at it (example):

`$env:USERPROFILE\Downloads\three.js-master\three.js-master`

Or set a project-local path via your own env / notes — **do not commit machine-specific absolute paths**.

- Prefer **project** `node_modules/three` (or `package.json` lock) when versions differ.
- Mirror may be newer than the project — **match project version** before pasting APIs.
- Deep-read only modules you need (e.g. CSM → `examples/jsm/csm/`). Do not ingest the whole tree.
- In-repo pointer: `llms.txt` → threejs.org docs.

### Quick route map

| Need | Look under mirror / package |
|---|---|
| Cascaded shadows (CSM) | `examples/jsm/csm/` |
| Lights / shadow maps | `src/lights/`, `src/renderers/webgl/` |
| Materials / PBR | `src/materials/` |
| Controls / helpers | `examples/jsm/controls/`, `examples/jsm/helpers/` |
| Postprocessing | `examples/jsm/postprocessing/` |
| Official examples | `examples/` |

## Suggested order when the task is 3D / Three.js

1. Confirm Three version from project `package.json`.
2. Run app → console + network first.
3. If scene/material/light/shadow needs truth → use `threejs-devtools-mcp` when available.
4. If API unsure → deep-read matching files from project `three` or local mirror.
5. Fix → rebuild → F12 → stepwise `visual_step` as required by gates.
6. Claim only through GODKILLER.

## Forbidden

- Shipping custom broken wrappers when official `examples/jsm/...` already solves it (study then integrate).
- Claiming Three.js-quality without runtime proof.
- Vendoring whole three.js into the GODKILLER package.
