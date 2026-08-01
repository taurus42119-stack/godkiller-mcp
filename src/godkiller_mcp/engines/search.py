"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

def _default_tools_dir() -> Optional[Path]:
    """Optional tools root from GODKILLER_TOOLS_DIR (never hardcode a user machine path)."""
    raw = os.environ.get("GODKILLER_TOOLS_DIR", "").strip()
    return Path(raw) if raw else None


def _find_dev_binary(name: str, custom_dir: Optional[str | Path] = None) -> Optional[str]:
    path_binary = shutil.which(name)
    if path_binary:
        return path_binary
    root = Path(custom_dir) if custom_dir else _default_tools_dir()
    if root:
        cpath = root / name / f"{name}.exe"
        if cpath.exists():
            return str(cpath)
        cpath_no_exe = root / name / name
        if cpath_no_exe.exists():
            return str(cpath_no_exe)
    return None


class HyperSearchEngine:
    """Ripgrep-inspired fast pattern search with Python regex fallback."""

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.rg_path = _find_dev_binary("rg", default_tools_dir)

    def search(self, pattern: str, search_path: str = ".", max_results: int = 100) -> Dict[str, Any]:
        root = Path(search_path)
        matches: List[Dict[str, Any]] = []
        if self.rg_path and root.exists():
            try:
                cmd = [self.rg_path, "--json", "-n", "--max-count", str(max_results), "--", pattern, str(root)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in proc.stdout.splitlines():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "match":
                            mdata = data.get("data", {})
                            matches.append({
                                "file": mdata.get("path", {}).get("text", ""),
                                "line": mdata.get("line_number", 0),
                                "text": mdata.get("lines", {}).get("text", "").strip()
                            })
                    except Exception:
                        pass
                return {"engine": "ripgrep_cli", "pattern": pattern, "count": len(matches), "matches": matches[:max_results]}
            except Exception:
                pass

        from godkiller_mcp.tool_hints import install_hint

        # Python Regex Fallback
        try:
            regex = re.compile(pattern, re.IGNORECASE)
            for pfile in root.rglob("*"):
                if len(matches) >= max_results:
                    break
                if pfile.is_file() and not any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist") for part in pfile.parts):
                    try:
                        content = pfile.read_text(encoding="utf-8", errors="ignore")
                        for i, line in enumerate(content.splitlines(), start=1):
                            if regex.search(line):
                                matches.append({
                                    "file": str(pfile),
                                    "line": i,
                                    "text": line.strip()
                                })
                                if len(matches) >= max_results:
                                    break
                    except Exception:
                        pass
        except Exception as e:
            return {
                "engine": "python_regex_fallback",
                "pattern": pattern,
                "error": str(e),
                "matches": [],
                "install_hint": install_hint("rg"),
            }

        return {
            "engine": "python_regex_fallback",
            "pattern": pattern,
            "count": len(matches),
            "matches": matches[:max_results],
            "install_hint": install_hint("rg"),
        }


class FastFindEngine:
    """fd-inspired fast file indexer with os.scandir fallback."""

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.fd_path = _find_dev_binary("fd", default_tools_dir)

    def find(self, name_pattern: str, search_path: str = ".", max_results: int = 100) -> Dict[str, Any]:
        root = Path(search_path)
        results: List[str] = []
        if self.fd_path and root.exists():
            try:
                cmd = [self.fd_path, "--hidden", "--exclude", ".git", "--exclude", "venv", "--exclude", "node_modules", name_pattern, str(root)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in proc.stdout.splitlines():
                    if line.strip():
                        results.append(line.strip())
                        if len(results) >= max_results:
                            break
                return {"engine": "fd_cli", "pattern": name_pattern, "count": len(results), "files": results}
            except Exception:
                pass

        # Python os.scandir Fallback
        pattern_lower = name_pattern.lower()

        def _scan(dir_path: Path):
            try:
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        if len(results) >= max_results:
                            return
                        if entry.name.startswith(".") or entry.name in ("venv", "__pycache__", "node_modules", "dist"):
                            continue
                        if pattern_lower in entry.name.lower():
                            results.append(entry.path)
                        if entry.is_dir(follow_symlinks=False):
                            _scan(Path(entry.path))
            except Exception:
                pass

        if root.exists():
            _scan(root)
        from godkiller_mcp.tool_hints import install_hint

        return {
            "engine": "python_scandir_fallback",
            "pattern": name_pattern,
            "count": len(results),
            "files": results,
            "install_hint": install_hint("fd"),
        }


class ContextPreviewEngine:
    """bat-inspired styled code context viewer with plain text fallback."""

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.bat_path = _find_dev_binary("bat", default_tools_dir)

    def preview(self, file_path: str, start_line: int = 1, end_line: int = 100) -> Dict[str, Any]:
        pfile = Path(file_path)
        if not pfile.exists():
            return {"error": f"File not found: {file_path}"}

        if self.bat_path:
            try:
                cmd = [self.bat_path, "--style=numbers", "--color=never", "-r", f"{start_line}:{end_line}", str(pfile)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if proc.returncode == 0 and proc.stdout:
                    return {"engine": "bat_cli", "file": str(pfile), "range": f"{start_line}-{end_line}", "content": proc.stdout}
            except Exception:
                pass

        # Python Line Reader Fallback
        try:
            content = pfile.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            total_lines = len(lines)
            selected = lines[max(0, start_line - 1) : min(total_lines, end_line)]
            formatted_lines = [f"{i:4d} | {line}" for i, line in enumerate(selected, start=max(1, start_line))]
            return {
                "engine": "python_reader_fallback",
                "file": str(pfile),
                "range": f"{start_line}-{end_line}",
                "total_lines": total_lines,
                "content": "\n".join(formatted_lines),
            }
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

