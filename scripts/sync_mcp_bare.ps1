# Sync Antigravity / Gemini MCP configs to the same honest inventory (no godkiller).
# Bare race posture: 3 servers. Re-run scripts/sync_mcp_with.ps1 to add godkiller as #4.
# Portable — resolves tools from PATH (override with JCODEMUNCH_MCP / CODEBASE_MEMORY_MCP).
$ErrorActionPreference = "Stop"

function Resolve-Tool([string]$EnvKey, [string]$DefaultName) {
  $explicit = [Environment]::GetEnvironmentVariable($EnvKey)
  if ($explicit -and (Test-Path $explicit)) { return $explicit }
  $cmd = Get-Command $DefaultName -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $DefaultName
}

$jcode = Resolve-Tool "JCODEMUNCH_MCP" "jcodemunch-mcp"
$cmem = Resolve-Tool "CODEBASE_MEMORY_MCP" "codebase-memory-mcp"

$cdt = if ($env:CHROME_DEVTOOLS_MCP_SPEC) { $env:CHROME_DEVTOOLS_MCP_SPEC } else { "chrome-devtools-mcp@0.6.0" }
$cfg = [ordered]@{
  mcpServers = [ordered]@{
    "chrome-devtools" = [ordered]@{
      command = "npx"
      args = @("-y", $cdt)
    }
    "jcodemunch-mcp" = [ordered]@{
      command = $jcode
      args = @()
    }
    "codebase-memory-mcp" = [ordered]@{
      command = $cmem
    }
  }
}
$three = ($cfg | ConvertTo-Json -Depth 6)

$paths = @(
  "$env:USERPROFILE\.gemini\config\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity\mcp\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity-ide\mcp_config.json"
)
foreach ($p in $paths) {
  $dir = Split-Path $p -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($p, $three.Trim() + "`n", $utf8)
  Write-Host "wrote $p"
}
Write-Host "Bare inventory synced (3 servers, no godkiller). Restart Antigravity."
Write-Host "jcodemunch=$jcode"
Write-Host "codebase-memory=$cmem"
