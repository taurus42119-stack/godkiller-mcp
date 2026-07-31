# Known limitations

Honest list so audits do not rediscover marketing gaps.

## Bounded (still)

| Area | Reality |
| --- | --- |
| MCP cannot force the host IDE | If Antigravity never calls kernel tools, gates do not run |
| LLM council needs API key | Set `GODKILLER_LLM_API_KEY` or `OPENAI_API_KEY` (+ optional `GODKILLER_LLM_BASE_URL` / `GODKILLER_LLM_MODEL`) |
| OCR for `expected_elements` | Needs `pytesseract` + Tesseract **or** sidecar `.txt`; else fail-closed |
| Verify allowlist | Default: pytest / unittest / ruff / mypy |
| `dispatch.py` | Still a large router; further splits ongoing |
| Legacy arena JSON | Hand-written “516 / 0.38s” files are **not** authoritative |

## Audit points → status

| Attack | Status |
| --- | --- |
| Exhaustive read `txt[:3000]` | **Fixed** — full read by default |
| Council only `eval(`/`exec(` | **Fixed** — LLM multi-agent debate (Coder/Hacker/Optimizer, 2 rounds) + static evidence briefing |
| Confidence fixed +20/+15 | **Fixed** — AST/symbol metrics |
| Self-heal if-elif only | **Fixed** — executes fallback tool |
| Visual critic regex only | **Fixed** — VisionBridge on disk + elements |
| DAG always success | **Fixed** — real tool execution |
| Hack 5 substrings | **Fixed** — allowlist |
| `expected_elements` unused | **Fixed** |
| No gauntlet / runner / grader | **Fixed** — `run_arena` + `grade_arena` + gauntlet suite |
| pytest_output header-only / 516@0.38s | **Fixed** — grader flags as suspicious; overall=0 |

## LLM council usage

```bash
# OpenAI-compatible
set GODKILLER_LLM_API_KEY=sk-...
set GODKILLER_LLM_MODEL=gpt-4o-mini
# optional: set GODKILLER_LLM_BASE_URL=https://api.openai.com/v1
```

Tool: `gk_code` action `council` / `godkiller_council_debate`  
Default `require_llm=true` — without a key returns `COUNCIL_BLOCKED_NO_LLM` (does not fake a debate).
