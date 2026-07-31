# Security Policy

## Supported versions

Security fixes land on the latest published `godkiller-mcp` release line.

## Reporting a vulnerability

Open a **private** GitHub security advisory:

https://github.com/taurus42119-stack/godkiller-mcp/security/advisories/new

Do **not** file public issues with exploit PoCs that enable RCE against third parties.
Social DMs are not a security intake path.

## Threat model (honest)

This package is an **MCP policy / proof kernel**. It hardens what happens when agents
call GODKILLER tools. It does **not** replace:

- Host OS access control / EDR
- IDE native Write without a PreToolUse hook (`docs/WRITE_GUARD_HOOKS.md`)
- Enterprise SSO, DLP, or managed device policy

Ship posture (required for hardened deployments):

```text
GODKILLER_PROFILE=ship
GODKILLER_SEAL_KEY=<64 hex chars>
GODKILLER_SEAL_REQUIRE_ENV=1
```

See `docs/SEAL_KEY.md`, `docs/HOST_VS_MCP.md`, and `PUBLISH.md`.

## Supply chain

- Dependabot watches pip + GitHub Actions (`.github/dependabot.yml`).
- CI runs on Ubuntu + Windows across Python 3.10–3.12.
- For release attestation, prefer generating an SBOM at publish time
  (`pip install cyclonedx-bom` → CycloneDX JSON) and attaching it to the GitHub Release —
  not claimed as SOC2 / enterprise procurement coverage.
