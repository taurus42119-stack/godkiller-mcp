# Changelog

## 1.1.1

MCP **proof-kernel** (Beta). Not Enterprise Ready / not OS lock / not procurement-grade.

**Mouth:** PyPI classifier `Development Status :: 4 - Beta`. Internal A/B does not
claim oracle wins vs Bare. Known gaps remain (god-dispatch, partial mypy/ruff scope).

- Vision: fail-closed OCR (no fake strings / no hardcoded user tesseract path)
- SSRF: `safe_urlopen` hop-by-hop; `llm_client` uses `safe_urlopen` (not raw urlopen)
- soak / verify_bundle / fault_probe: allowlist + deny path escape (pytest/unittest/**ruff/mypy**)
- fault_probe: `detect_hacking(..., cwd=workspace)`
- Policy: ship ignores kill-switches that weaken gates (`WRITE_GUARD` / DOI off)
- Swarm: server-side scout auto + ultradeep `require_swarm`; edit gate
- `/debug` Self-CTF: workspace-only attack loop; blocks fix until findings
- Seal: require host `GODKILLER_SEAL_KEY` (no silent `.seal_key` mint)
- Visual GREEN requires `expected_elements`; score_11 dims 5–11 sealed-only
- Hook artifact: `godkiller_mcp/hooks/pretooluse_write_guard.json`
- Docs: honest Beta + A/B mouth

## 1.1.0

- Prior public release line
