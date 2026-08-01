"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.engines.search import _find_dev_binary


class AstGrepEngine:
    """ast-grep inspired structural pattern search & refactoring engine."""

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.sg_path = _find_dev_binary("ast-grep", default_tools_dir) or _find_dev_binary("sg", default_tools_dir)

    def search(
        self,
        pattern: str,
        search_path: str = ".",
        lang: str = "python",
        max_results: int = 50,
    ) -> Dict[str, Any]:
        root = Path(search_path)
        matches: List[Dict[str, Any]] = []

        if self.sg_path and root.exists():
            try:
                cmd = [self.sg_path, "run", "--lang", lang, "--pattern", pattern, "--json", str(root)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.stdout:
                    for line in proc.stdout.splitlines():
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if isinstance(data, dict):
                                    matches.append(data)
                                elif isinstance(data, list):
                                    matches.extend(data)
                            except Exception:
                                pass
                    if matches:
                        return {"engine": "ast_grep_cli", "pattern": pattern, "count": len(matches), "matches": matches[:max_results]}
            except Exception:
                pass

        # Python AST Structural Matcher Fallback
        escaped_pat = re.escape(pattern)
        pattern_clean = escaped_pat.replace(r"\$A", r"\w+").replace(r"\$ARGS", r".*").replace(r"\$FUNC", r"\w+")
        try:
            regex = re.compile(pattern_clean, re.IGNORECASE)
            for pfile in root.rglob("*.py"):
                if len(matches) >= max_results:
                    break
                if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist") for part in pfile.parts):
                    continue
                try:
                    content = pfile.read_text(encoding="utf-8", errors="ignore")
                    tree = ast.parse(content, filename=str(pfile))
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Call, ast.FunctionDef, ast.ClassDef)):
                            line_no = getattr(node, "lineno", 0)
                            line_text = content.splitlines()[line_no - 1] if 0 < line_no <= len(content.splitlines()) else ""
                            if regex.search(line_text):
                                matches.append({
                                    "file": str(pfile),
                                    "line": line_no,
                                    "text": line_text.strip(),
                                    "node_type": type(node).__name__,
                                })
                                if len(matches) >= max_results:
                                    break
                except Exception:
                    pass
        except Exception as e:
            return {"engine": "python_ast_fallback", "pattern": pattern, "error": str(e), "matches": []}

        return {"engine": "python_ast_fallback", "pattern": pattern, "count": len(matches), "matches": matches[:max_results]}

