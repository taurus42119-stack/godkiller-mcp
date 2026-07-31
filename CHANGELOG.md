# Changelog

## 1.1.1

MCP proof-kernel hardening sync. Not an enterprise-procurement claim.
PyPI classifier: Production/Stable (still not Enterprise Ready).

- SSRF: `safe_urlopen` hop-by-hop redirect revalidation; browser post-nav/click URL guards
- soak_run / verify_bundle: allowlist + deny path escape outside workspace
- Policy: ship ignores kill-switches that weaken gates (`WRITE_GUARD` / DOI off)
- Swarm: server-side scout auto + ultradeep `require_swarm`; edit gate
- `/debug` Self-CTF: workspace-only attack loop; blocks fix until findings
- Seal: require host `GODKILLER_SEAL_KEY` (no silent `.seal_key` mint)
- Visual GREEN requires `expected_elements`; score_11 dims 5–11 sealed-only
- Hook artifact: `godkiller_mcp/hooks/pretooluse_write_guard.json`
- Docs: proof-kernel mouth (no Beta label); suite count 476+

## 1.1.0

- Prior public release line
