"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class AutoFixEngine:
    """Experimental regex find/replace (not a real AST rewriter). Ship forces preview."""

    def fix(
        self,
        file_path: str,
        pattern: str,
        replacement: str,
        preview_only: bool = True,
        workspace_root: str | Path | None = None,
    ) -> Dict[str, Any]:
        from godkiller_mcp.code_intel import check_edit_safe
        from godkiller_mcp.ship_mode import relax_enabled

        forced_preview = False
        if not relax_enabled():
            if not preview_only:
                forced_preview = True
            preview_only = True

        pfile = Path(file_path)
        if not pfile.exists():
            return {"error": f"File not found: {file_path}"}

        ws = Path(workspace_root) if workspace_root else pfile.resolve().parent
        gate = check_edit_safe([str(pfile)], ws)
        if not gate.payload.get("safe"):
            return {
                "error": "check_edit_safe blocked write",
                "edit_safe": gate.payload,
                "engine": "regex_autofix",
                "preview_only": True,
                "replacements_made": 0,
            }

        try:
            content = pfile.read_text(encoding="utf-8", errors="ignore")
            escaped_pat = re.escape(pattern)
            pat_regex = escaped_pat.replace(r"\$A", r"([^)]+)").replace(r"\$ARGS", r"(.*)").replace(r"\$FUNC", r"(\w+)")
            sub_replacement = replacement.replace("$A", r"\1").replace("$ARGS", r"\1").replace("$FUNC", r"\1")

            new_content, count = re.subn(pat_regex, sub_replacement, content)

            diff_lines: List[str] = []
            if count > 0:
                diff_lines = [
                    f"--- {file_path} (original)",
                    f"+++ {file_path} (modified)",
                    f"@@ Replaced {count} occurrences @@",
                ]

            if not preview_only and count > 0:
                pfile.write_text(new_content, encoding="utf-8")

            out = {
                "engine": "regex_autofix",
                "tier": "experimental",
                "file": str(pfile),
                "pattern": pattern,
                "replacement": replacement,
                "replacements_made": count,
                "preview_only": preview_only,
                "edit_safe": gate.payload,
                "diff": "\n".join(diff_lines) if diff_lines else "No matches found to replace.",
            }
            if forced_preview:
                out["forced_preview"] = True
                out["reason"] = "ship/non-relax forces preview_only — disk write blocked"
            return out
        except Exception as e:
            return {"error": f"Failed auto-fix: {e}"}
