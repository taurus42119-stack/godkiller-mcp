# Sync Antigravity / Gemini MCP configs: Bare 3 + godkiller as #4 (WITH posture).
# Also registers the full agent skills tree via ~/.gemini/config/skills.json
# and points GODKILLER_SKILLS_ROOTS at the same roots for gk_mode.skill_catalog.
$ErrorActionPreference = "Stop"

$py = "C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe"
$pkg = "C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\godkiller_mcp_pypi_package"
$skillsWorkspace = "C:\Users\ASUS\Desktop\ANTIGRAVITY MCP\.agents\skills"
$writer = Join-Path $pkg "scripts\_write_antigravity_mcp.py"

if (-not (Test-Path $py)) { throw "Python 3.12 not found: $py" }
if (-not (Test-Path $pkg)) { throw "Package path missing: $pkg" }
if (-not (Test-Path $skillsWorkspace)) { throw "Skills root missing: $skillsWorkspace" }
if (-not (Test-Path $writer)) { throw "Writer missing: $writer" }

Write-Host "Ensuring editable godkiller-mcp on Python 3.12..."
& $py -m pip install --no-cache-dir -e $pkg | Out-Host
if ($LASTEXITCODE -ne 0) { throw "pip install -e failed" }

$cfgDir = Join-Path $env:USERPROFILE ".gemini\config"
New-Item -ItemType Directory -Force -Path $cfgDir | Out-Null
$sealFile = Join-Path $cfgDir "godkiller_seal_key.txt"
if (-not (Test-Path $sealFile)) {
  $seal = (& $py -c "import secrets; print(secrets.token_hex(32))").Trim()
  # ascii no BOM
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

& $py $writer
if ($LASTEXITCODE -ne 0) { throw "writer failed" }

Write-Host ""
Write-Host "WITH inventory synced (4 servers incl. godkiller) + skills.json."
Write-Host "Restart Antigravity, then call gk_meta.status / gk_honesty_status."
