# Sync Antigravity / Gemini MCP configs to the same honest inventory (no godkiller).
# Bare race posture: 3 servers. Re-run scripts/sync_mcp_with.ps1 to add godkiller as #4.
$ErrorActionPreference = "Stop"
$three = @'
{
  "mcpServers": {
    "chrome-devtools": {
      "command": "npx",
      "args": ["-y", "chrome-devtools-mcp@latest"]
    },
    "jcodemunch-mcp": {
      "command": "C:\\Users\\ASUS\\AppData\\Local\\Programs\\Python\\Python312\\Scripts\\jcodemunch-mcp.exe",
      "args": []
    },
    "codebase-memory-mcp": {
      "command": "C:\\Users\\ASUS\\AppData\\Local\\Programs\\codebase-memory-mcp\\codebase-memory-mcp.exe"
    }
  }
}
'@
$paths = @(
  "$env:USERPROFILE\.gemini\config\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity\mcp\mcp_config.json",
  "$env:USERPROFILE\.gemini\antigravity-ide\mcp_config.json"
)
foreach ($p in $paths) {
  $dir = Split-Path $p -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  # UTF-8 without BOM (BOM breaks some JSON readers on mcpServers key)
  $utf8 = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($p, $three.Trim() + "`n", $utf8)
  Write-Host "wrote $p"
}
Write-Host "Bare inventory synced (3 servers, no godkiller). Restart Antigravity."
