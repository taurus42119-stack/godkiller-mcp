# Publishing godkiller-mcp (MCP proof kernel — not Enterprise Ready)

## Preconditions

- Version in `pyproject.toml` / `__init__.py` matches `CHANGELOG.md`
- `pytest -q` green
- A/B Antigravity: either done **or** still marked OPEN in `logs/harsh_scorecard.md` (honest)

## Local build

```bash
pip install build twine
python -m build
twine check dist/*
```

## SBOM (CycloneDX)

```bash
pip install cyclonedx-bom
cyclonedx-py environment -o sbom.cdx.json
```

CI: `.github/workflows/sbom.yml` on `v*` tags / workflow_dispatch. Attach `sbom.cdx.json` to the GitHub Release.

## PyPI Trusted Publishing (preferred)

`publish.yml` already uses OIDC (`id-token: write`) via `pypa/gh-action-pypi-publish`.
On release it also builds CycloneDX SBOM and tries to attach `sbom.cdx.json` to the GitHub Release.

**Hold:** do not create the GitHub Release / tag until you greenlight L4 (after L3 A/B or honest OPEN scorecard).

1. On PyPI: create a Trusted Publisher for this GitHub repo + `publish.yml`
2. Create a GitHub Release / tag `vX.Y.Z` → workflow publishes
3. Do **not** put long-lived `PYPI_API_TOKEN` in secrets unless Trusted Publishing is unavailable
4. PyPI description mouth = **MCP proof kernel** — never Enterprise Ready

Fallback (token):

```bash
$env:UV_PUBLISH_TOKEN = "pypi-..."
uv publish
```

## Ship posture reminder (users)

```bash
export GODKILLER_PROFILE=ship
export GODKILLER_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export GODKILLER_SEAL_REQUIRE_ENV=1
# + host PreToolUse → godkiller-write-guard --stdin
```
