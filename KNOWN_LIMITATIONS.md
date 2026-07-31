# Known limitations

Honest list so audits do not rediscover marketing gaps.

## Still true / bounded

| Area | Reality |
| --- | --- |
| MCP cannot force the host IDE | If Antigravity never calls kernel tools, gates do not run |
| Council | Multi-pass **static AST** analysis — not LLM multi-agent debate |
| OCR for `expected_elements` | Needs `pytesseract` + Tesseract **or** a sidecar `.txt`; otherwise fail-closed |
| Verify allowlist | Default: pytest / unittest / ruff / mypy only (extend code to add more) |
| `claim_done` extra gates | Search/skill/quality loops still accept structured agent evidence beyond verify_bundle |
| `dispatch.py` | Still a large router; handlers package is scaffolding for further splits |
| Legacy arena JSON | Files under `arena_logs/` that claim “516 in 0.38s” without a runner are **not** authoritative — use `python -m benchmarks.run_arena` |

## Fixed relative to common audit points

| Attack | Status |
| --- | --- |
| Exhaustive read truncated to 3000 chars silently | Fixed — full read by default; truncate only if `max_chars_per_file` set |
| Council only checks `eval(`/`exec(` | Fixed — security + structure + complexity AST passes |
| Confidence fixed +20/+15 | Fixed — AST/symbol hit-rate metrics |
| Pipeline always `success` without running | Fixed — executes tool handlers when `execute=true` |
| Self-heal substring only | Fixed — diagnoses then **runs** fallback tool |
| `expected_elements` unused | Fixed — OCR/sidecar matching, fail-closed |
| Visual critic regex-only | Fixed — optional on-disk VisionBridge merge |
| Hack filter five silly substrings | Fixed — command allowlist |
| No gauntlet / no runner | Fixed — `benchmarks/gauntlet` + `benchmarks/run_arena.py` |
