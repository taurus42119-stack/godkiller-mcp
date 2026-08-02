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
allowlisted commands (e.g. pytest / unittest / ruff / mypy) inside the workspace via
`safe_exec` (`shell=False`). **Claim-grade verify in-core is Python-test oriented** —
JS/TS/Go projects need host/CI oracles outside this allowlist. That is not remote RCE by
design, but it **is** local code execution of the project under test — treat untrusted
workspaces accordingly. `fault_probe` applies mutants only under a disposable **shadow
copy** of the workspace (SIGKILL cannot leave mutants in the live tree). Legacy
`.godkiller/probe_unclean.json` leftovers still block facades until
`godkiller-restore` succeeds.

**Shared GODKILLER_HOME:** use one HOME per host process/session (README install).
Task JSON persist takes an advisory `tasks.lock` under the tasks dir — reduces
clobber races but is **not** multi-tenant isolation. Concurrent hosts sharing
one HOME can still contend; `fault_probe` also holds `probe.lock`. Do not claim
multi-tenant safety.

**State root:** mutable `.godkiller` state prefers `GODKILLER_HOME`, else
`<workspace|GODKILLER_WORKSPACE|cwd>/.godkiller`. Silent `~/.godkiller` fallback
is **refused** when cwd is `$HOME` unless `GODKILLER_ALLOW_HOME_STATE=1` or
`GODKILLER_HOME` is set explicitly.

**Sandbox / theatre notes (Beta):** MCP path tools use `path_gate_error` against
`GODKILLER_WORKSPACE` (preferred) or cwd — **unpinned `$HOME` cwd is refused**.
Passing `root=` / explicit workspace into the gate **cannot rebind** the jail
(attacker `$HOME` → `workspace_root_rebinding_refused`).
`write_guard` status is `hook_hint_only` until `GODKILLER_WRITE_GUARD_PROVEN` after a live
PreToolUse test (file markers ≠ enforcement). `write_guard` allowlists are exact/prefix
only (no basename-only match). Agent-supplied competitor URLs are advisory, not claim-armor,
unless `require_attested_competitor=1`. Host-mode council is labeled `theatre_risk` and
does not count as ship armor unless `GODKILLER_ALLOW_HOST_COUNCIL=1`.

Ship posture (required for hardened deployments):

```text
GODKILLER_PROFILE=ship
GODKILLER_SEAL_KEY=<64 hex chars>
GODKILLER_SEAL_REQUIRE_ENV=1
GODKILLER_WORKSPACE=<project root>
# After live PreToolUse deny/allow test only:
GODKILLER_WRITE_GUARD_PROVEN=1
```

Without a proven host write-guard, do **not** claim native Write is forced.

See `docs/SEAL_KEY.md`, `docs/HOST_VS_MCP.md`, and `docs/WRITE_GUARD_HOOKS.md`.

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
