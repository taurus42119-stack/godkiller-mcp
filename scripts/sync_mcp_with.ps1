# Sync Antigravity / Gemini MCP configs: Bare 3 + godkiller as #4 (WITH posture).
# Portable — no machine-specific absolute paths.
# Optional env: GODKILLER_WORKSPACE, GODKILLER_PYTHON
$ErrorActionPreference = "Stop"

$pkg = Split-Path -Parent $PSScriptRoot
$workspace = if ($env:GODKILLER_WORKSPACE) {
  $env:GODKILLER_WORKSPACE
} else {
  Split-Path -Parent $pkg
}
$skillsWorkspace = Join-Path $workspace ".agents\skills"
$writer = Join-Path $pkg "scripts\_write_antigravity_mcp.py"

function Resolve-Python {
  if ($env:GODKILLER_PYTHON -and (Test-Path $env:GODKILLER_PYTHON)) {
    return $env:GODKILLER_PYTHON
  }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "Python not found on PATH. Set GODKILLER_PYTHON to a python.exe."
}

$py = Resolve-Python

if (-not (Test-Path $pkg)) { throw "Package path missing: $pkg" }
if (-not (Test-Path $skillsWorkspace)) { throw "Skills root missing: $skillsWorkspace (set GODKILLER_WORKSPACE)" }
if (-not (Test-Path $writer)) { throw "Writer missing: $writer" }

Write-Host "Using python: $py"
Write-Host "Package: $pkg"
Write-Host "Workspace: $workspace"
Write-Host "Ensuring editable godkiller-mcp..."
& $py -m pip install --no-cache-dir -e $pkg | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip install -e failed" }

$cfgDir = Join-Path $env:USERPROFILE ".gemini\config"
New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
$sealFile = Join-Path $cfgDir "godkiller_seal_key.txt"
if (-not (Test-Path $sealFile)) {
  $seal = (& $py -c "import secrets; print(secrets.token_hex(32))").Trim()
  [System.IO.File]::WriteAllText($sealFile, $seal)
  Write-Host "created $sealFile"
} else {
  $seal = (Get-Content -Path $sealFile -Raw).Trim()
  Write-Host "reusing $sealFile"
}
if ($seal.Length -lt 32) { throw "Seal key too short in $sealFile" }

$skillsRootsEnv = @(
  $skillsWorkspace,
  (Join-Path $skillsWorkspace "agent-ops"),
  (Join-Path $pkg ".agents\skills"),
  (Join-Path $pkg "src\godkiller_mcp\bundled_skills"),
  (Join-Path $pkg "src\godkiller_mcp\bundled_skills\agent-ops")
) | Where-Object { Test-Path $_ } | Select-Object -Unique
$skillsRootsEnv = ($skillsRootsEnv -join ";")

$env:GK_SEAL = $seal
$env:GK_SKILLS = $skillsRootsEnv
$env:GODKILLER_SEAL_KEY = $seal
$env:GODKILLER_SKILLS_ROOTS = $skillsRootsEnv
$env:GODKILLER_PROFILE = "ship"
$env:GODKILLER_WORKSPACE = $workspace

& $py $writer
if ($LASTEXITCODE -ne 0) { throw "writer failed" }

# A-light: drop write-guard hook artifact + heartbeat marker (warns in gk_meta.status if missing)
& $py -m godkiller_mcp.write_guard install --target godkiller --workspace $workspace --force | Out-Host
& $py -m godkiller_mcp.write_guard install --target cursor --workspace $workspace --force | Out-Host
$env:GODKILLER_WRITE_GUARD_WIRED = "1"

Write-Host ""
Write-Host "WITH inventory synced (4 servers incl. godkiller) + skills.json + write-guard hook files."
Write-Host "Wire host PreToolUse -> godkiller-write-guard --stdin (see docs/WRITE_GUARD_HOOKS.md)."
Write-Host "Restart Antigravity, then call gk_meta.status / gk_honesty_status."
