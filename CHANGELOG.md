# Changelog

## 1.1.1

Hardening sync (GitHub Beta). Not an enterprise-procurement claim.

- SSRF: `safe_urlopen` hop-by-hop redirect revalidation; browser post-nav/click URL guards
- soak_run / verify_bundle: allowlist + deny path escape outside workspace
- Policy: ship ignores kill-switches that weaken gates (`WRITE_GUARD` / DOI off)
- Swarm: server-side scout auto + ultradeep `require_swarm`; edit gate
- `/debug` Self-CTF: workspace-only attack loop; blocks fix until findings
- Seal: ship profile force-require env (no silent soft-fail)
- Hook artifact: `godkiller_mcp/hooks/pretooluse_write_guard.json`
- visual_critic evidence sealed as server_authored
- Docs: scrub machine-local paths; suite count 450

## 1.1.0

- Prior public Beta line
