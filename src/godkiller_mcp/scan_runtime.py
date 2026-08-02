"""Optional Semgrep scanner + clear engine reporting (workspace-gated)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from godkiller_mcp.code_intel import SecurityScanEngine, _find_dev_binary
from godkiller_mcp.path_sandbox import path_gate_error, workspace_root


def run_semgrep(target_path: str = ".", config: str = "auto") -> Dict[str, Any]:
    """Scan only under workspace. Outside paths → path_outside_workspace (no snippets)."""
    raw = str(target_path or ".").strip() or "."
    try:
        target = str(workspace_root()) if raw in (".",) else raw
    except Exception as exc:
        return {"ok": False, "error": "workspace_root_unpinned", "detail": str(exc)}
    bad = path_gate_error(target)
    if bad:
        return bad

    root = Path(target).resolve()
    binary = _find_dev_binary("semgrep") or shutil.which("semgrep")
    if not binary:
        fallback = SecurityScanEngine().scan(str(root))
        fallback["note"] = "semgrep not on PATH; used python_security_rules_fallback"
        fallback["workspace"] = str(workspace_root())
        return fallback
    try:
        proc = subprocess.run(
            [binary, "scan", "--json", "--config", config, str(root)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        data: Any
        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError:
            data = {"raw_stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}
        return {
            "engine": "semgrep",
            "exit_code": proc.returncode,
            "target": str(root),
            "workspace": str(workspace_root()),
            "result": data,
        }
    except Exception as exc:
        fallback = SecurityScanEngine().scan(str(root))
        fallback["semgrep_error"] = str(exc)
        fallback["workspace"] = str(workspace_root())
        return fallback
