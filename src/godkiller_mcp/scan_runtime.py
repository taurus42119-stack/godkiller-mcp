"""Optional Semgrep scanner + clear engine reporting."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from godkiller_mcp.code_intel import SecurityScanEngine, _find_dev_binary


def run_semgrep(target_path: str = ".", config: str = "auto") -> Dict[str, Any]:
    root = Path(target_path)
    binary = _find_dev_binary("semgrep") or shutil.which("semgrep")
    if not binary:
        fallback = SecurityScanEngine().scan(str(root))
        fallback["note"] = "semgrep not on PATH; used python_security_rules_fallback"
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
            "result": data,
        }
    except Exception as exc:
        fallback = SecurityScanEngine().scan(str(root))
        fallback["semgrep_error"] = str(exc)
        return fallback
