# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| Latest published `1.1.x` | Yes — security fixes land here |
| Older `1.x` / `0.x` | Best-effort only — upgrade to latest |

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

**Intentional workspace process execution:** `verify_bundle` and `fault_probe` may run
allowlisted commands (e.g. pytest) inside the workspace via `safe_exec` (`shell=False`).
That is not remote RCE by design, but it **is** local code execution of the project under
test — treat untrusted workspaces accordingly. `fault_probe` mutates via backup under
`.godkiller/probe_backup` + unclean marker; SIGKILL can still leave mutants until the next
probe/claim restore pass.

**Sandbox / theatre notes (Beta):** MCP path tools (including `visual_step`) use
`path_gate_error` against cwd/workspace. `write_guard` allowlists are exact/prefix only
(no basename-only match). Agent-supplied competitor URLs are advisory, not claim-armor,
unless `require_attested_competitor=1`. Host-mode council is labeled `theatre_risk` and
does not count as ship armor unless `GODKILLER_ALLOW_HOST_COUNCIL=1`.

Ship posture (required for hardened deployments):

```text
GODKILLER_PROFILE=ship
GODKILLER_SEAL_KEY=<64 hex chars>
GODKILLER_SEAL_REQUIRE_ENV=1
```

See `docs/SEAL_KEY.md`, `docs/HOST_VS_MCP.md`, and `PUBLISH.md`.

Generate a seal key:

```text
python -c "import secrets; print(secrets.token_hex(32))"
```

After a crashed `fault_probe`, restore mutants with:

```text
godkiller-restore --workspace .
godkiller-restore --check
```


## Supply chain

- Dependabot watches pip + GitHub Actions (`.github/dependabot.yml`).
- CI runs on Ubuntu + Windows across Python 3.10–3.12.
- For release attestation, prefer generating an SBOM at publish time
  (`pip install cyclonedx-bom` → CycloneDX JSON) and attaching it to the GitHub Release —
  not claimed as SOC2 / enterprise procurement coverage.
