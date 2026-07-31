"""Code intelligence helpers: blast radius, failing slice parsing, edit safety checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from godkiller_mcp.schema import EvidenceType


@dataclass
class SymbolRef:
    name: str
    file: str = ""
    line: int = 0


@dataclass
class FailingSliceReport:
    raw_output: str
    files: List[str] = field(default_factory=list)
    symbols: List[SymbolRef] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"Files: {len(self.files)}, Symbols: {len(self.symbols)}"

    def to_evidence_payload(self) -> dict:
        return {
            "files": self.files,
            "symbols": [{"name": s.name, "file": s.file, "line": s.line} for s in self.symbols],
        }


@dataclass
class BlastRadiusReport:
    symbol: str
    files: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return f"Symbol: {self.symbol}, Files: {len(self.files)}, Dependents: {len(self.dependents)}"

    def to_evidence_payload(self) -> dict:
        return {
            "symbol": self.symbol,
            "files": self.files,
            "dependents": self.dependents,
        }


@dataclass
class EditSafeResult:
    target_files: List[str]
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        return f"Target files: {len(self.target_files)}"

    def to_evidence_payload(self) -> dict:
        return {"target_files": self.target_files, **self.payload}


def require_blast_before_edit(
    evidence_types: List[EvidenceType] | Set[EvidenceType],
) -> Tuple[bool, str]:
    if EvidenceType.BLAST_RADIUS in evidence_types:
        return True, "blast_radius evidence found"
    return False, "BLAST_RADIUS evidence required before editing code in task"


def get_failing_slice(output: str, workspace_root: Optional[str | Path] = None) -> FailingSliceReport:
    files: List[str] = []
    symbols: List[SymbolRef] = []

    file_matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)', output)
    for filepath, line_str, sym_name in file_matches:
        if filepath not in files:
            files.append(filepath)
        symbols.append(SymbolRef(name=sym_name, file=filepath, line=int(line_str)))

    failed_matches = re.findall(r"FAILED (\S+)::(\w+)", output)
    for test_file, test_func in failed_matches:
        if test_file not in files:
            files.append(test_file)
        symbols.append(SymbolRef(name=test_func, file=test_file, line=0))

    return FailingSliceReport(raw_output=output, files=files, symbols=symbols)


def blast_radius(symbol: str, workspace_root: str | Path) -> BlastRadiusReport:
    root = Path(workspace_root)
    affected_files: List[str] = []
    dependents: List[str] = []

    if root.exists():
        for py_file in root.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if symbol in content:
                    rel_path = str(py_file.relative_to(root))
                    affected_files.append(rel_path)
                    dependents.append(rel_path)
            except Exception:
                pass

    return BlastRadiusReport(
        symbol=symbol, files=affected_files, dependents=dependents
    )


def check_edit_safe(
    target_files: List[str], workspace_root: str | Path
) -> EditSafeResult:
    """Reject paths outside workspace (including escape via .. / absolute)."""
    root = Path(workspace_root).resolve()
    reasons: List[str] = []
    resolved: List[str] = []

    if not target_files:
        return EditSafeResult(
            target_files=[],
            payload={"safe": False, "files_checked": 0, "reasons": ["no target files"]},
        )

    for raw in target_files:
        p = Path(raw)
        candidate = p if p.is_absolute() else (root / p)
        try:
            resolved_path = candidate.resolve()
            resolved_path.relative_to(root)
        except (OSError, ValueError):
            reasons.append(f"outside_workspace:{raw}")
            continue
        resolved.append(str(resolved_path))

    safe = len(reasons) == 0 and len(resolved) == len(target_files)
    return EditSafeResult(
        target_files=target_files,
        payload={
            "safe": safe,
            "files_checked": len(target_files),
            "resolved": resolved,
            "reasons": reasons,
            "workspace": str(root),
        },
    )


# --- Code helpers (search / map / heuristics) ---
import ast
import json
import os
import shutil
import subprocess


@dataclass
class Tag:
    name: str
    kind: str  # "class", "def", "import"
    file: str
    line: int


class RepoMapGenerator:
    """Aider-inspired Repo Map generator using AST parsing & symbol tagging."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def generate_tags(self) -> List[Tag]:
        tags: List[Tag] = []
        if not self.root.exists():
            return tags
        for py_file in self.root.rglob("*.py"):
            if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist") for part in py_file.parts):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_file))
                rel_path = str(py_file.relative_to(self.root))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        tags.append(Tag(name=node.name, kind="class", file=rel_path, line=node.lineno))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        tags.append(Tag(name=node.name, kind="def", file=rel_path, line=node.lineno))
            except Exception:
                pass
        return tags

    def get_repo_map(self, max_tokens: int = 1000) -> str:
        tags = self.generate_tags()
        files_map: Dict[str, List[Tag]] = {}
        for t in tags:
            files_map.setdefault(t.file, []).append(t)

        lines: List[str] = [f"=== GODKILLER REPO MAP ({len(tags)} symbols across {len(files_map)} files) ==="]
        for fpath, file_tags in files_map.items():
            lines.append(f"\n📄 {fpath}:")
            for t in file_tags:
                prefix = "  class" if t.kind == "class" else "  def"
                lines.append(f"{prefix} {t.name} (L{t.line})")

        full_text = "\n".join(lines)
        if len(full_text) > max_tokens * 4:
            full_text = full_text[: max_tokens * 4] + "\n... [Repo Map Truncated for Token Limit]"
        return full_text


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
            return {"engine": "python_regex_fallback", "pattern": pattern, "error": str(e), "matches": []}

        return {"engine": "python_regex_fallback", "pattern": pattern, "count": len(matches), "matches": matches[:max_results]}


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
        return {"engine": "python_scandir_fallback", "pattern": name_pattern, "count": len(results), "files": results}


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


class SecurityScanEngine:
    """Best-effort regex CWE heuristics; optional snyk CLI if installed."""

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.snyk_path = _find_dev_binary("snyk", default_tools_dir)

    def scan(self, target_path: str = ".", severity_threshold: str = "medium") -> Dict[str, Any]:
        root = Path(target_path)
        issues: List[Dict[str, Any]] = []

        if self.snyk_path and root.exists():
            try:
                cmd = [self.snyk_path, "code", "test", "--json", f"--severity-threshold={severity_threshold}", str(root)]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if proc.stdout:
                    try:
                        data = json.loads(proc.stdout)
                        return {"engine": "snyk_cli", "raw": data}
                    except Exception:
                        pass
            except Exception:
                pass

        # Python AST Security Scanner Fallback (Checks OWASP Top Vulnerabilities)
        vulnerability_rules = [
            (r"\beval\s*\(", "CWE-95", "Use of eval() detected (Code Injection hazard)", "HIGH"),
            (r"\bexec\s*\(", "CWE-95", "Use of exec() detected (Code Injection hazard)", "HIGH"),
            (r"shell\s*=\s*True", "CWE-78", "subprocess call with shell=True detected (OS Command Injection hazard)", "HIGH"),
            (r"yaml\.load\s*\([^,)]*\)", "CWE-502", "Insecure yaml.load() detected without SafeLoader", "MEDIUM"),
            (r"(password|secret|api_key)\s*=\s*['\"][^'\"]+['\"]", "CWE-798", "Possible hardcoded secret detected", "MEDIUM"),
        ]

        if root.exists():
            for pfile in root.rglob("*.py"):
                if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist") for part in pfile.parts):
                    continue
                try:
                    content = pfile.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()
                    for line_idx, line in enumerate(lines, start=1):
                        for pattern, cwe, desc, severity in vulnerability_rules:
                            if re.search(pattern, line):
                                issues.append({
                                    "file": str(pfile),
                                    "line": line_idx,
                                    "cwe": cwe,
                                    "issue": desc,
                                    "severity": severity,
                                    "snippet": line.strip(),
                                })
                except Exception:
                    pass

        return {
            "engine": "python_security_rules_fallback",
            "target": str(root),
            "total_issues": len(issues),
            "issues": issues,
        }


import traceback


class DeepScrapeEngine:
    """Firecrawl-inspired web scraper & HTML-to-clean-LLM-markdown converter."""

    def scrape(self, url_or_html: str, max_length: int = 5000) -> Dict[str, Any]:
        if url_or_html.startswith("http://") or url_or_html.startswith("https://"):
            if any(forbidden in url_or_html for forbidden in ["127.0.0.1", "localhost", "0.0.0.0", "169.254."]):
                return {"error": "Access to local/loopback IP is restricted for security."}
            try:
                import urllib.request
                req = urllib.request.Request(url_or_html, headers={"User-Agent": "GODKILLER-Agent/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html_content = resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                return {"error": f"Failed to fetch URL: {e}"}
        else:
            html_content = url_or_html

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            for elem in soup(["script", "style", "nav", "footer", "header", "aside", "svg"]):
                elem.decompose()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_md = "\n".join(lines)
            if len(clean_md) > max_length:
                clean_md = clean_md[:max_length] + "\n... [Content Truncated for Token Limit]"
            return {"engine": "bs4_cleaner", "markdown": clean_md, "length": len(clean_md)}
        except Exception:
            pass

        clean_text = re.sub(r"<(script|style).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        clean_md = "\n".join(lines)
        if len(clean_md) > max_length:
            clean_md = clean_md[:max_length] + "\n... [Content Truncated for Token Limit]"
        return {"engine": "python_regex_stripper_fallback", "markdown": clean_md, "length": len(clean_md)}


class LogTraceEngine:
    """Sentry/Postman-inspired Traceback Exception & Log Parser."""

    def parse_log(self, log_output: str) -> Dict[str, Any]:
        frames: List[Dict[str, Any]] = []
        matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)\n\s*(.*)', log_output)
        for filepath, lineno, func, snippet in matches:
            frames.append({
                "file": filepath,
                "line": int(lineno),
                "function": func,
                "snippet": snippet.strip(),
            })

        exc_match = re.search(r'([A-Za-z_]\w*Error|[A-Za-z_]\w*Exception):\s*(.*)', log_output)
        exc_type = exc_match.group(1) if exc_match else "UnknownException"
        exc_msg = exc_match.group(2) if exc_match else (log_output.strip().splitlines()[-1] if log_output.strip() else "")

        return {
            "engine": "traceback_parser",
            "exception_type": exc_type,
            "message": exc_msg,
            "frame_count": len(frames),
            "stack_frames": frames,
        }


class AutoFixEngine:
    """Experimental regex find/replace (not a real AST rewriter)."""

    def fix(
        self,
        file_path: str,
        pattern: str,
        replacement: str,
        preview_only: bool = True,
    ) -> Dict[str, Any]:
        pfile = Path(file_path)
        if not pfile.exists():
            return {"error": f"File not found: {file_path}"}

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

            return {
                "engine": "regex_autofix",
                "tier": "experimental",
                "file": str(pfile),
                "pattern": pattern,
                "replacement": replacement,
                "replacements_made": count,
                "preview_only": preview_only,
                "diff": "\n".join(diff_lines) if diff_lines else "No matches found to replace.",
            }
        except Exception as e:
            return {"error": f"Failed auto-fix: {e}"}


import graphlib


class PipelineRunner:
    """DAG executor that actually invokes tool handlers (not dry-run mark-success)."""

    async def run_pipeline(
        self,
        steps: List[Dict[str, Any]],
        executor: Any = None,
    ) -> Dict[str, Any]:
        """
        executor: async callable(tool_name: str, args: dict) -> list|dict|str
        If omitted, returns planned order only (explicit dry_run).
        """
        results = []
        pipeline_context: Dict[str, Any] = {}

        graph = {}
        for idx, step in enumerate(steps):
            deps = step.get("depends_on", [])
            graph[idx] = set(deps)

        try:
            ts = graphlib.TopologicalSorter(graph)
            order = list(ts.static_order())
        except Exception as e:
            return {"error": f"Invalid DAG structure: {e}", "engine": "pipeline_executor"}

        if executor is None:
            return {
                "engine": "pipeline_executor",
                "dry_run": True,
                "note": "No executor provided — steps not run. Pass MCP handle_tool as executor.",
                "total_steps": len(steps),
                "execution_order": order,
                "results": [
                    {"step": i, "name": steps[i].get("name", "unknown"), "status": "planned_not_executed"}
                    for i in order
                ],
            }

        for step_idx in order:
            step = steps[step_idx]
            name = step.get("name") or step.get("tool") or "unknown"
            args = dict(step.get("args") or {})

            for k, v in list(args.items()):
                if isinstance(v, str) and v.startswith("$"):
                    ctx_key = v[1:]
                    if ctx_key in pipeline_context:
                        args[k] = pipeline_context[ctx_key]

            try:
                raw = await executor(name, args)
                if isinstance(raw, list) and raw and hasattr(raw[0], "text"):
                    body = raw[0].text
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                else:
                    parsed = raw
                status = "success"
                if isinstance(parsed, dict) and parsed.get("error"):
                    status = "error"
                step_result = {
                    "step": step_idx,
                    "name": name,
                    "status": status,
                    "args": args,
                    "output": parsed,
                }
            except Exception as exc:
                step_result = {
                    "step": step_idx,
                    "name": name,
                    "status": "error",
                    "args": args,
                    "error": str(exc),
                }
                if step.get("stop_on_error", True):
                    pipeline_context[f"step_{step_idx}_output"] = step_result
                    results.append(step_result)
                    return {
                        "engine": "pipeline_executor",
                        "dry_run": False,
                        "total_steps": len(steps),
                        "execution_order": order,
                        "results": results,
                        "aborted_at": step_idx,
                    }

            pipeline_context[f"step_{step_idx}_output"] = step_result
            results.append(step_result)

        return {
            "engine": "pipeline_executor",
            "dry_run": False,
            "total_steps": len(steps),
            "execution_order": order,
            "results": results,
            "all_ok": all(r.get("status") == "success" for r in results),
        }


class SelfHealingEngine:
    """Diagnose failure, suggest fallback tool, optionally execute it."""

    def diagnose(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        task_context = task_context or {}
        err = (error_or_output or "").lower()

        if failed_tool in ("godkiller_hyper_search", "ripgrep") or "no matches" in err:
            return {
                "diagnosis": "Search returned no matches; try structural search.",
                "recommended_tool": "godkiller_ast_grep",
                "remediated_args": {
                    "pattern": task_context.get("pattern", "def $FUNC($$$ARGS)"),
                    "search_path": task_context.get("search_path", "."),
                },
            }
        if "syntaxerror" in err or "traceback" in err or "exception" in err:
            return {
                "diagnosis": "Exception/traceback text detected; parse frames.",
                "recommended_tool": "godkiller_log_trace",
                "remediated_args": {"log_output": error_or_output},
            }
        if "not found" in err or "no such file" in err:
            return {
                "diagnosis": "Missing path; remap repository symbols.",
                "recommended_tool": "godkiller_repo_map",
                "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
            }
        return {
            "diagnosis": "Unspecified failure; remap repo before retrying.",
            "recommended_tool": "godkiller_repo_map",
            "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
        }

    def heal(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plan = self.diagnose(failed_tool, error_or_output, task_context)
        return {
            "engine": "self_heal_executor",
            "action": "SUGGEST_AND_OPTIONAL_RUN",
            "executed": False,
            **plan,
        }

    async def heal_and_run(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
        executor: Any = None,
    ) -> Dict[str, Any]:
        plan = self.diagnose(failed_tool, error_or_output, task_context)
        out: Dict[str, Any] = {
            "engine": "self_heal_executor",
            "action": "EXECUTED_FALLBACK" if executor else "SUGGEST_ONLY",
            **plan,
            "executed": False,
        }
        if executor is None:
            return out
        raw = await executor(plan["recommended_tool"], plan["remediated_args"])
        if isinstance(raw, list) and raw and hasattr(raw[0], "text"):
            try:
                out["fallback_output"] = json.loads(raw[0].text)
            except Exception:
                out["fallback_output"] = raw[0].text
        else:
            out["fallback_output"] = raw
        out["executed"] = True
        return out


class EpistemicConfidenceGate:
    """Edit readiness from file AST + symbol hit-rate (not fixed +20/+15)."""

    def evaluate(
        self,
        file_path: str,
        known_symbols: List[str],
        has_searched: bool,
        search_hit_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        pfile = Path(file_path)
        metrics: Dict[str, Any] = {
            "file_exists": pfile.exists(),
            "byte_size": 0,
            "ast_parse_ok": False,
            "def_count": 0,
            "class_count": 0,
            "symbol_hit_rate": 0.0,
            "symbols_requested": len(known_symbols or []),
            "symbols_found_in_file": 0,
            "search_done": bool(has_searched),
            "search_hit_count": search_hit_count,
        }
        reasons: List[str] = []

        if not pfile.exists():
            return {
                "engine": "edit_readiness_metrics",
                "file": file_path,
                "metrics": metrics,
                "score": 0.0,
                "allowed_to_edit": False,
                "missing": ["file_exists"],
                "reasons": ["File does not exist"],
                "recommendation": "BLOCK_EDIT_FORCE_RECON",
            }

        try:
            text = pfile.read_text(encoding="utf-8", errors="ignore")
            metrics["byte_size"] = len(text.encode("utf-8"))
            tree = ast.parse(text)
            metrics["ast_parse_ok"] = True
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    metrics["def_count"] += 1
                elif isinstance(node, ast.ClassDef):
                    metrics["class_count"] += 1
            found = 0
            for sym in known_symbols or []:
                if sym and sym in text:
                    found += 1
            metrics["symbols_found_in_file"] = found
            if known_symbols:
                metrics["symbol_hit_rate"] = found / max(len(known_symbols), 1)
            else:
                metrics["symbol_hit_rate"] = 0.0
        except SyntaxError as e:
            reasons.append(f"AST parse failed: {e}")
            metrics["ast_parse_ok"] = False
        except Exception as e:
            reasons.append(f"Read/analyze failed: {e}")

        # Weighted score from measured quantities (0..100)
        score = 0.0
        if metrics["file_exists"]:
            score += 25.0
        if metrics["ast_parse_ok"]:
            score += 25.0
        score += min(20.0, metrics["symbol_hit_rate"] * 20.0)
        if metrics["def_count"] + metrics["class_count"] > 0:
            score += 10.0
        if has_searched:
            score += 10.0
        if search_hit_count is not None:
            score += min(10.0, float(search_hit_count) * 2.0)
        elif has_searched:
            score += 5.0

        missing = []
        if not metrics["file_exists"]:
            missing.append("file_exists")
        if not metrics["ast_parse_ok"]:
            missing.append("ast_parse_ok")
        if known_symbols and metrics["symbol_hit_rate"] < 0.5:
            missing.append("symbol_hit_rate>=0.5")
        if not has_searched:
            missing.append("search_done")

        allowed = score >= 70.0 and metrics["ast_parse_ok"] and has_searched
        return {
            "engine": "edit_readiness_metrics",
            "file": file_path,
            "metrics": metrics,
            "score": round(score, 2),
            "threshold": 70.0,
            "allowed_to_edit": allowed,
            "missing": missing,
            "reasons": reasons,
            "recommendation": "PROCEED" if allowed else "BLOCK_EDIT_FORCE_RECON",
        }


import concurrent.futures


class ExhaustiveReaderEngine:
    """Full-file directory reader. Truncation only when max_chars_per_file is set."""

    def read_all(
        self,
        dir_path: str,
        max_files: int = 200,
        max_chars_per_file: Optional[int] = None,
    ) -> Dict[str, Any]:
        root = Path(dir_path)
        if not root.exists():
            return {"error": f"Directory path does not exist: {dir_path}"}

        file_list: List[Path] = []
        if root.is_file():
            file_list.append(root)
        else:
            for pfile in root.rglob("*"):
                if pfile.is_file():
                    if any(
                        part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist")
                        for part in pfile.parts
                    ):
                        continue
                    file_list.append(pfile)

        truncated_listing = len(file_list) > max_files
        file_list = file_list[:max_files]
        contents: Dict[str, str] = {}
        truncated_files: List[str] = []
        total_bytes = 0

        def _read_single(p: Path) -> Tuple[str, str, bool, int]:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                raw_len = len(txt)
                was_trunc = False
                if max_chars_per_file is not None and raw_len > max_chars_per_file:
                    txt = txt[:max_chars_per_file]
                    was_trunc = True
                return (str(p), txt, was_trunc, raw_len)
            except Exception as e:
                return (str(p), f"[Error reading file: {e}]", False, 0)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            for path_str, txt, was_trunc, raw_len in executor.map(_read_single, file_list):
                contents[path_str] = txt
                total_bytes += raw_len
                if was_trunc:
                    truncated_files.append(path_str)

        return {
            "engine": "exhaustive_reader_engine",
            "target": str(root),
            "total_files_read": len(contents),
            "files": list(contents.keys()),
            "contents": contents,
            "full_content": max_chars_per_file is None,
            "max_chars_per_file": max_chars_per_file,
            "truncated_files": truncated_files,
            "truncated_file_listing": truncated_listing,
            "total_bytes_on_disk": total_bytes,
        }


class AutoSkillifyEngine:
    """Generates reusable SKILL.md in .agents/skills/<skill_name>/ upon task completion."""

    def skillify(
        self,
        skill_name: str,
        description: str,
        instructions: str,
        workspace_root: str = ".",
    ) -> Dict[str, Any]:
        skill_dir = Path(workspace_root) / ".agents" / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"

        content = f"""---
name: {skill_name}
description: {description}
---

# {skill_name.replace('-', ' ').title()}

## Overview
{description}

## Instructions & Protocol
{instructions}
"""
        skill_file.write_text(content, encoding="utf-8")
        return {
            "engine": "auto_skillify_engine",
            "skill_name": skill_name,
            "file": str(skill_file),
            "status": "created",
        }


class CouncilDebateEngine:
    """Multi-pass static analysis council (coder/structure, hacker/security, optimizer/complexity)."""

    def debate(
        self,
        proposed_code_or_plan: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = context or {}
        text = proposed_code_or_plan or ""
        coder: Dict[str, Any] = {"role": "coder", "findings": [], "ok": True}
        hacker: Dict[str, Any] = {"role": "hacker", "findings": [], "ok": True}
        optimizer: Dict[str, Any] = {"role": "optimizer", "findings": [], "ok": True}

        # --- Hacker pass: security patterns on source or free text ---
        security_rules = [
            (r"\beval\s*\(", "CWE-95 eval()"),
            (r"\bexec\s*\(", "CWE-95 exec()"),
            (r"shell\s*=\s*True", "CWE-78 shell=True"),
            (r"pickle\.loads\s*\(", "CWE-502 pickle.loads"),
            (r"yaml\.load\s*\([^,\)]*\)", "CWE-502 yaml.load without Loader"),
            (r"(password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]", "CWE-798 hardcoded secret"),
        ]
        for pat, label in security_rules:
            if re.search(pat, text, re.I):
                hacker["findings"].append(label)
                hacker["ok"] = False

        # --- Coder + Optimizer passes via AST when parseable ---
        tree = None
        try:
            tree = ast.parse(text)
            coder["findings"].append("AST parse OK — treating input as Python")
        except SyntaxError:
            coder["findings"].append("Not valid Python AST — structure pass limited to text heuristics")
            if len(text.strip()) < 20:
                coder["ok"] = False
                coder["findings"].append("Proposal too short to review")

        if tree is not None:
            funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
            coder["findings"].append(f"defs={len(funcs)} classes={len(classes)} try_blocks={len(tries)}")
            if funcs and len(tries) == 0 and any(
                "open(" in ast.dump(f) or "urlopen" in ast.dump(f) for f in funcs
            ):
                coder["findings"].append("I/O without try/except detected")
                coder["ok"] = False

            # nesting / length
            max_depth = 0

            def _depth(node: ast.AST, d: int = 0) -> None:
                nonlocal max_depth
                max_depth = max(max_depth, d)
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef)):
                        _depth(child, d + 1)
                    else:
                        _depth(child, d)

            _depth(tree)
            long_funcs = []
            for f in funcs:
                try:
                    span = (f.end_lineno or f.lineno) - f.lineno + 1
                except Exception:
                    span = 0
                if span > 80:
                    long_funcs.append(f"{f.name}:{span}L")
            optimizer["findings"].append(f"max_nesting_depth={max_depth}")
            if max_depth >= 6:
                optimizer["findings"].append("Deep nesting (>=6) — consider refactor")
                optimizer["ok"] = False
            if long_funcs:
                optimizer["findings"].append(f"Long functions: {long_funcs}")
                optimizer["ok"] = False
            if not long_funcs and max_depth < 6:
                optimizer["findings"].append("Complexity within soft bounds")

        consensus = bool(coder["ok"] and hacker["ok"] and optimizer["ok"])
        return {
            "engine": "static_analysis_council",
            "coder": coder,
            "hacker": hacker,
            "optimizer": optimizer,
            "consensus_reached": consensus,
            "verdict": "COUNCIL_PASS" if consensus else "COUNCIL_REJECT",
            "passes": {
                "structure": coder["ok"],
                "security": hacker["ok"],
                "complexity": optimizer["ok"],
            },
        }





