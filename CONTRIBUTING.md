# Contributing

MCP proof kernel. Prefer fixes that close gates in code, not README essays.

1. `pip install -e ".[dev,scrape]"`
2. `GODKILLER_DOI_RESOLVE=0 GODKILLER_SEAL_QUIET=1 pytest -q`
3. Do not commit `.godkiller/`, `.seal_key`, `.env`, or machine-local paths
4. Security: GitHub Security Advisories — see `SECURITY.md`
