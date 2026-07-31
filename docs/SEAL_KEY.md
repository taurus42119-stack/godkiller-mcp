# Seal key — host env (required) vs legacy file (opt-in, off-ship)

Armor evidences (`verify_bundle`, `fault_probe`, council, …) are HMAC-sealed so
casual edits to `task_*.json` on disk do not unlock claim gates.

## Preferred: host environment

```bash
# 32-byte key as 64 hex chars
export GODKILLER_SEAL_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"

# Optional: refuse any workspace key path entirely
export GODKILLER_SEAL_REQUIRE_ENV=1
```

PowerShell:

```powershell
$env:GODKILLER_SEAL_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:GODKILLER_SEAL_REQUIRE_ENV = "1"
```

While `GODKILLER_SEAL_KEY` is set:

- That value is the authority (hex or any passphrase → SHA-256 derived)
- Workspace `persist_dir/.seal_key` is **ignored**
- A marker file `.seal_key_SOURCE` may appear explaining env ownership

**Default:** the kernel does **not** auto-create `.seal_key`. Missing env → hard error pointing here.

## Ship posture

With `GODKILLER_PROFILE=ship`, only `GODKILLER_SEAL_KEY` is accepted.
`GODKILLER_ALLOW_LEGACY_SEAL` is ignored under ship.

## Legacy `.seal_key` (off-ship compat only)

To **read** an existing workspace key without minting a new one:

```bash
export GODKILLER_ALLOW_LEGACY_SEAL=1
# do not set GODKILLER_PROFILE=ship
```

Migrate:

1. Read existing key bytes (do not commit them):
   `python -c "print(open('PATH/to/tasks/.seal_key','rb').read().hex())"`
2. Set `GODKILLER_SEAL_KEY` to that hex (keeps old seals verifying)
3. Set `GODKILLER_SEAL_REQUIRE_ENV=1`
4. Delete or ignore workspace `.seal_key` after confirming tasks load

If you rotate to a **new** env key, old sealed evidence will scrub on reload (fail-closed) — re-run verify/council.

## Threat model (honest)

- Env key beats “edit JSON in workspace” for agents that only write project files
- An agent/OS with full host env access can still steal the key — this is not an OS kernel
- Without host PreToolUse, native Write still bypasses MCP — see `WRITE_GUARD_HOOKS.md`
