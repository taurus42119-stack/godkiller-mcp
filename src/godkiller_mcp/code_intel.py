"""Code intelligence helpers: blast radius, failing slice parsing, edit safety checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from godkiller_mcp.schema import EvidenceType
from godkiller_mcp.council_agents import CouncilDebateEngine

__all__ = [
    "SymbolRef",
    "FailingSliceReport",
    "BlastRadiusReport",
    "EditSafeResult",
    "require_blast_before_edit",
    "get_failing_slice",
    "blast_radius",
    "check_edit_safe",
    "RepoMapGenerator",
    "HyperSearchEngine",
    "FastFindEngine",
    "ContextPreviewEngine",
    "AstGrepEngine",
    "SecurityScanEngine",
    "DeepScrapeEngine",
    "LogTraceEngine",
    "AutoFixEngine",
    "PipelineRunner",
    "SelfHealingEngine",
    "EpistemicConfidenceGate",
    "ExhaustiveReaderEngine",
    "AutoSkillifyEngine",
    "CouncilDebateEngine",
]

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
        extra = getattr(self, "payload_extra", None) or {}
        return {
            "symbol": self.symbol,
            "files": self.files,
            "dependents": self.dependents,
            **extra,
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
    """Find files that reference ``symbol`` via AST (optional ripgrep candidate filter)."""
    import ast
    import re
    import subprocess

    root = Path(workspace_root)
    affected_files: List[str] = []
    engine = "python_ast"
    sym = (symbol or "").strip()
    if not sym or not root.exists():
        return BlastRadiusReport(symbol=symbol, files=[], dependents=[])

    skip_parts = {"venv", "__pycache__", "node_modules", "dist", ".git"}

    def _skip(p: Path) -> bool:
        return any(part.startswith(".") or part in skip_parts for part in p.parts)

    candidates: Optional[List[Path]] = None
    rg = _find_dev_binary("rg")
    if rg:
        try:
            cmd = [rg, "-l", "--glob", "*.py", "-w", "--", sym, str(root)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            candidates = []
            for line in proc.stdout.splitlines():
                p = Path(line.strip())
                if p.is_file() and not _skip(p):
                    candidates.append(p)
            engine = "ripgrep+ast"
        except Exception:
            candidates = None
            engine = "python_ast"

    name_re = re.compile(rf"(?<!\w){re.escape(sym)}(?!\w)")

    class _Hit(ast.NodeVisitor):
        def __init__(self) -> None:
            self.hit = False

        def visit_Name(self, node: ast.Name) -> None:
            if node.id == sym:
                self.hit = True
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if node.attr == sym:
                self.hit = True
            self.generic_visit(node)

        def visit_alias(self, node: ast.alias) -> None:
            parts = (node.name or "").split(".")
            if node.name == sym or node.asname == sym or sym in parts:
                self.hit = True
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node.name == sym:
                self.hit = True
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node.name == sym:
                self.hit = True
            self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == sym:
                self.hit = True
            self.generic_visit(node)

    files_iter = candidates if candidates is not None else [
        p for p in root.rglob("*.py") if not _skip(p)
    ]

    used_regex = False
    for py_file in files_iter:
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hit = False
        try:
            tree = ast.parse(content, filename=str(py_file))
            visitor = _Hit()
            visitor.visit(tree)
            hit = visitor.hit
        except SyntaxError:
            if name_re.search(content):
                hit = True
                used_regex = True
        if hit:
            try:
                rel = str(py_file.resolve().relative_to(root.resolve()))
            except ValueError:
                rel = str(py_file)
            if rel not in affected_files:
                affected_files.append(rel)

    if used_regex and engine == "python_ast":
        engine = "regex_fallback"
    elif used_regex and engine == "ripgrep+ast":
        engine = "ripgrep+ast+regex"

    report = BlastRadiusReport(symbol=symbol, files=affected_files, dependents=list(affected_files))
    report.payload_extra = {"engine": engine}  # type: ignore[attr-defined]
    return report


def check_edit_safe(
    target_files: List[str], workspace_root: str | Path
) -> EditSafeResult:
    """Reject paths outside workspace (including escape via .. / absolute / ~)."""
    root = Path(workspace_root).resolve()
    reasons: List[str] = []
    resolved: List[str] = []

    if not target_files:
        return EditSafeResult(
            target_files=[],
            payload={"safe": False, "files_checked": 0, "reasons": ["no target files"]},
        )

    for raw in target_files:
        s = str(raw)
        if s.startswith("~") or s.startswith("~/") or s.startswith("~\\"):
            reasons.append(f"home_escape:{raw}")
            continue
        p = Path(s)
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
    """Best-effort AST CWE heuristics; optional snyk/bandit CLI if installed.

    Not a professional SAST / Semgrep org scan — kernel signal only.
    """

    def __init__(self, default_tools_dir: Optional[str | Path] = None):
        self.snyk_path = _find_dev_binary("snyk", default_tools_dir)
        self.bandit_path = _find_dev_binary("bandit", default_tools_dir)

    def scan(self, target_path: str = ".", severity_threshold: str = "medium") -> Dict[str, Any]:
        root = Path(target_path)
        issues: List[Dict[str, Any]] = []

        if self.snyk_path and root.exists():
            try:
                cmd = [
                    self.snyk_path,
                    "code",
                    "test",
                    "--json",
                    f"--severity-threshold={severity_threshold}",
                    str(root),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if proc.stdout:
                    try:
                        data = json.loads(proc.stdout)
                        return {"engine": "snyk_cli", "raw": data}
                    except Exception:
                        pass
            except Exception:
                pass

        if self.bandit_path and root.exists():
            try:
                cmd = [self.bandit_path, "-r", str(root), "-f", "json", "-q"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.stdout:
                    try:
                        data = json.loads(proc.stdout)
                        return {"engine": "bandit_cli", "raw": data, "note": "signal_not_org_sast"}
                    except Exception:
                        pass
            except Exception:
                pass

        if root.exists():
            for pfile in root.rglob("*.py"):
                if any(
                    part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist")
                    for part in pfile.parts
                ):
                    continue
                try:
                    content = pfile.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                try:
                    tree = ast.parse(content, filename=str(pfile))
                except SyntaxError:
                    # Unparseable: last-resort line regex (narrow)
                    issues.extend(_regex_security_fallback(pfile, content))
                    continue
                visitor = _AstSecurityVisitor(str(pfile), content.splitlines())
                visitor.visit(tree)
                issues.extend(visitor.issues)

        return {
            "engine": "python_ast_security",
            "target": str(root),
            "total_issues": len(issues),
            "issues": issues,
            "note": "ast_signal_not_professional_sast",
        }


_SECRET_NAME = re.compile(r"(password|secret|api_key|apikey|token|passwd)", re.I)


class _AstSecurityVisitor(ast.NodeVisitor):
    def __init__(self, path: str, lines: List[str]):
        self.path = path
        self.lines = lines
        self.issues: List[Dict[str, Any]] = []

    def _snip(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()
        return ""

    def _add(self, lineno: int, cwe: str, issue: str, severity: str) -> None:
        self.issues.append(
            {
                "file": self.path,
                "line": lineno,
                "cwe": cwe,
                "issue": issue,
                "severity": severity,
                "snippet": self._snip(lineno),
            }
        )

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in ("eval", "exec"):
            self._add(
                getattr(node, "lineno", 1),
                "CWE-95",
                f"Use of {name}() detected (Code Injection hazard)",
                "HIGH",
            )
        if name == "compile":
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and kw.value.value == "exec":
                    self._add(
                        getattr(node, "lineno", 1),
                        "CWE-95",
                        "compile(..., mode='exec') detected",
                        "HIGH",
                    )
        if name in ("os.system", "os.popen"):
            self._add(
                getattr(node, "lineno", 1),
                "CWE-78",
                f"{name}() detected (OS Command Injection hazard)",
                "HIGH",
            )
        if name.startswith("subprocess.") or name in (
            "subprocess.run",
            "subprocess.Popen",
            "subprocess.call",
            "subprocess.check_call",
            "subprocess.check_output",
        ):
            for kw in node.keywords:
                if kw.arg == "shell" and _is_true_const(kw.value):
                    self._add(
                        getattr(node, "lineno", 1),
                        "CWE-78",
                        "subprocess call with shell=True detected (OS Command Injection hazard)",
                        "HIGH",
                    )
        if name == "yaml.load":
            has_loader = any(kw.arg == "Loader" for kw in node.keywords)
            if not has_loader:
                self._add(
                    getattr(node, "lineno", 1),
                    "CWE-502",
                    "Insecure yaml.load() detected without Loader= (use safe_load)",
                    "MEDIUM",
                )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str) and node.value.value:
            for t in node.targets:
                tname = _target_name(t)
                if tname and _SECRET_NAME.search(tname):
                    self._add(
                        getattr(node, "lineno", 1),
                        "CWE-798",
                        f"Possible hardcoded secret in assignment to {tname}",
                        "MEDIUM",
                    )
        self.generic_visit(node)


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        base = _call_name(func.value)
        return f"{base}.{func.attr}" if base else func.attr
    return ""


def _target_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _is_true_const(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _regex_security_fallback(pfile: Path, content: str) -> List[Dict[str, Any]]:
    rules = [
        (r"\beval\s*\(", "CWE-95", "Use of eval() detected (Code Injection hazard)", "HIGH"),
        (r"\bexec\s*\(", "CWE-95", "Use of exec() detected (Code Injection hazard)", "HIGH"),
        (r"shell\s*=\s*True", "CWE-78", "subprocess call with shell=True detected", "HIGH"),
    ]
    out: List[Dict[str, Any]] = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for pattern, cwe, desc, severity in rules:
            if re.search(pattern, line):
                out.append(
                    {
                        "file": str(pfile),
                        "line": line_idx,
                        "cwe": cwe,
                        "issue": desc,
                        "severity": severity,
                        "snippet": line.strip(),
                    }
                )
    return out




class DeepScrapeEngine:
    """Web scraper that converts HTML to clean markdown for LLM context."""

    def scrape(self, url_or_html: str, max_length: int = 5000) -> Dict[str, Any]:
        if url_or_html.startswith("http://") or url_or_html.startswith("https://"):
            from godkiller_mcp.ssrf import assert_public_url

            ok, reason = assert_public_url(url_or_html)
            if not ok:
                return {"error": reason, "ssrf_blocked": True}
            try:
                from godkiller_mcp.ssrf import SafeHTTPError, safe_urlopen

                with safe_urlopen(
                    url_or_html,
                    timeout=10,
                    headers={"User-Agent": "GODKILLER-Agent/2.0"},
                ) as resp:
                    html_content = resp.read().decode("utf-8", errors="ignore")
            except SafeHTTPError as e:
                return {"error": e.reason, "ssrf_blocked": True}
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
    """Experimental regex find/replace (not a real AST rewriter). Ship forces preview."""

    def fix(
        self,
        file_path: str,
        pattern: str,
        replacement: str,
        preview_only: bool = True,
    ) -> Dict[str, Any]:
        from godkiller_mcp.ship_mode import relax_enabled

        forced_preview = False
        if not relax_enabled():
            if not preview_only:
                forced_preview = True
            preview_only = True

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

            out = {
                "engine": "regex_autofix",
                "tier": "experimental",
                "file": str(pfile),
                "pattern": pattern,
                "replacement": replacement,
                "replacements_made": count,
                "preview_only": preview_only,
                "diff": "\n".join(diff_lines) if diff_lines else "No matches found to replace.",
            }
            if forced_preview:
                out["forced_preview"] = True
                out["reason"] = "ship/non-relax forces preview_only — disk write blocked"
            return out
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
    """
    Failure recovery: parse traceback structure, map tool→fallback, optionally run it.

    Not magic auto-repair. Diagnose is structured (frames / exception / path existence),
    then one explicit fallback tool is executed when an executor is provided.
    """

    # Explicit tool routing — not a free-form substring soup.
    _TOOL_FALLBACK = {
        "godkiller_hyper_search": "godkiller_ast_grep",
        "ripgrep": "godkiller_ast_grep",
        "godkiller_fast_find": "godkiller_repo_map",
        "godkiller_ast_grep": "godkiller_repo_map",
        "godkiller_context_preview": "godkiller_exhaustive_read",
    }

    def _parse_traceback(self, text: str) -> Dict[str, Any]:
        return LogTraceEngine().parse_log(text or "")

    def _existing_frame_files(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        checked = []
        for fr in frames[:12]:
            path = fr.get("file") or ""
            exists = bool(path) and Path(path).is_file()
            checked.append({**fr, "exists_on_disk": exists})
        return checked

    def diagnose(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        task_context = task_context or {}
        raw = error_or_output or ""
        parsed = self._parse_traceback(raw)
        frames = self._existing_frame_files(parsed.get("stack_frames") or [])
        missing_frames = [f for f in frames if not f.get("exists_on_disk")]
        exc = parsed.get("exception_type") or "UnknownException"
        msg = (parsed.get("message") or "").strip()

        signals = {
            "exception_type": exc,
            "message": msg[:300],
            "frame_count": len(frames),
            "missing_frame_files": len(missing_frames),
            "failed_tool": failed_tool,
            "has_traceback_frames": bool(frames),
        }

        # 1) Structured traceback → parse frames (always preferred when frames exist)
        if frames or exc not in ("UnknownException",) and "Error" in exc:
            return {
                "diagnosis": (
                    f"Structured traceback: {exc}: {msg[:120]} "
                    f"({len(frames)} frame(s), {len(missing_frames)} missing on disk)."
                ),
                "recommended_tool": "godkiller_log_trace",
                "remediated_args": {"log_output": raw},
                "signals": signals,
                "frames": frames,
                "method": "traceback_parse",
            }

        # 2) Explicit missing path in context
        candidate = task_context.get("path") or task_context.get("file_path")
        if candidate and not Path(str(candidate)).exists():
            return {
                "diagnosis": f"Path missing on disk: {candidate}",
                "recommended_tool": "godkiller_repo_map",
                "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
                "signals": {**signals, "missing_path": str(candidate)},
                "method": "path_exists_check",
            }

        # 3) Known tool failure → fixed fallback map
        if failed_tool in self._TOOL_FALLBACK:
            fb = self._TOOL_FALLBACK[failed_tool]
            if fb == "godkiller_ast_grep":
                args = {
                    "pattern": task_context.get("pattern", "def $FUNC($$$ARGS)"),
                    "search_path": task_context.get("search_path", "."),
                }
            elif fb == "godkiller_exhaustive_read":
                args = {"dir_path": task_context.get("dir_path") or task_context.get("root_dir", ".")}
            else:
                args = {"root_dir": task_context.get("root_dir", ".")}
            return {
                "diagnosis": f"Tool '{failed_tool}' failed; explicit fallback '{fb}'.",
                "recommended_tool": fb,
                "remediated_args": args,
                "signals": signals,
                "method": "tool_fallback_map",
            }

        # 4) OS-level missing file language in message (last resort, after structure)
        low = raw.lower()
        if "no such file" in low or "filenotfounderror" in low or "errno 2" in low:
            return {
                "diagnosis": "FileNotFound-class failure; remap repository.",
                "recommended_tool": "godkiller_repo_map",
                "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
                "signals": signals,
                "method": "filenotfound_signal",
            }

        return {
            "diagnosis": "No structured traceback or known tool map hit; remap before retry.",
            "recommended_tool": "godkiller_repo_map",
            "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
            "signals": signals,
            "method": "default_remap",
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
            "tier": "recovery",
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
            "tier": "recovery",
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
        # Confirm heal produced structured output when we routed to log_trace
        if plan.get("recommended_tool") == "godkiller_log_trace" and isinstance(
            out.get("fallback_output"), dict
        ):
            out["heal_verified"] = bool(out["fallback_output"].get("exception_type"))
        else:
            out["heal_verified"] = out["executed"]
        return out


class EpistemicConfidenceGate:
    """Edit readiness heuristic (NOT Bayesian). Named weights; require symbol or search hit."""

    W_FILE = 25.0
    W_AST = 25.0
    W_SYM = 20.0
    W_DEFS = 10.0
    W_SEARCH = 10.0
    W_HITS = 10.0
    W_SEARCH_FALLBACK = 5.0
    THRESHOLD = 70.0

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
                "threshold": self.THRESHOLD,
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

        score = 0.0
        if metrics["file_exists"]:
            score += self.W_FILE
        if metrics["ast_parse_ok"]:
            score += self.W_AST
        score += min(self.W_SYM, metrics["symbol_hit_rate"] * self.W_SYM)
        if metrics["def_count"] + metrics["class_count"] > 0:
            score += self.W_DEFS
        if has_searched:
            score += self.W_SEARCH
        if search_hit_count is not None:
            score += min(self.W_HITS, float(search_hit_count) * 2.0)
        elif has_searched:
            score += self.W_SEARCH_FALLBACK

        missing = []
        if not metrics["file_exists"]:
            missing.append("file_exists")
        if not metrics["ast_parse_ok"]:
            missing.append("ast_parse_ok")
        if known_symbols and metrics["symbol_hit_rate"] < 0.5:
            missing.append("symbol_hit_rate>=0.5")
        if not has_searched:
            missing.append("search_done")
        hit_ok = float(metrics["symbol_hit_rate"] or 0) > 0 or (
            search_hit_count is not None and int(search_hit_count) > 0
        )
        if not hit_ok:
            missing.append("symbol_hit_rate>0_or_search_hit_count>0")

        allowed = (
            score >= self.THRESHOLD
            and metrics["ast_parse_ok"]
            and has_searched
            and hit_ok
        )
        res: Dict[str, Any] = {
            "engine": "edit_readiness_metrics",
            "file": file_path,
            "metrics": metrics,
            "score": round(score, 2),
            "threshold": self.THRESHOLD,
            "weights": {
                "file": self.W_FILE,
                "ast": self.W_AST,
                "sym": self.W_SYM,
                "defs": self.W_DEFS,
                "search": self.W_SEARCH,
                "hits": self.W_HITS,
            },
            "allowed_to_edit": allowed,
            "missing": missing,
            "reasons": reasons,
            "recommendation": "PROCEED" if allowed else "BLOCK_EDIT_FORCE_RECON",
            "honest": "heuristic weights — not Bayesian / not formal verification",
            "confidence_pct": round(score, 2),
        }
        from godkiller_mcp.view_propose import build_view_study_proposal, should_propose_view

        res["propose_view_study"] = should_propose_view(score)
        if res["propose_view_study"]:
            res["view_study"] = build_view_study_proposal(
                goal=f"edit readiness for {file_path}",
                confidence_pct=score,
                known_gaps=missing or reasons,
                topics=[
                    "similar file/module in a public reference repo",
                    "tests showing expected API for this path",
                ],
            )
            res["order"] = (
                "Confidence < 99%: IMMEDIATELY propose VIEW study (exemplar repos/files) "
                "to the user — do not silently invent the design. Call gk_mode.view_propose_study."
            )
        return res


import concurrent.futures
import os as _os


class ExhaustiveReaderEngine:
    """Full-file directory reader with byte budget (fail-visible when exceeded)."""

    DEFAULT_MAX_TOTAL_BYTES = 32_000_000

    def read_all(
        self,
        dir_path: str,
        max_files: int = 200,
        max_chars_per_file: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        root = Path(dir_path)
        if not root.exists():
            return {"error": f"Directory path does not exist: {dir_path}"}

        budget = int(max_total_bytes if max_total_bytes is not None else self.DEFAULT_MAX_TOTAL_BYTES)
        workers_env = _os.environ.get("GODKILLER_EXHAUSTIVE_WORKERS", "").strip()
        workers = int(max_workers if max_workers is not None else (workers_env or 10))
        workers = max(1, min(workers, 32))

        file_list: List[Path] = []
        skipped_binary: List[str] = []
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
                    # Skip obvious binaries by suffix
                    if pfile.suffix.lower() in (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".webp",
                        ".pdf",
                        ".zip",
                        ".exe",
                        ".dll",
                        ".so",
                        ".pyc",
                        ".whl",
                    ):
                        skipped_binary.append(str(pfile))
                        continue
                    file_list.append(pfile)

        truncated_listing = len(file_list) > max_files
        file_list = file_list[:max_files]
        contents: Dict[str, str] = {}
        truncated_files: List[str] = []
        total_bytes = 0
        budget_exceeded = False

        def _read_single(p: Path) -> Tuple[str, str, bool, int, bool]:
            try:
                # Peek binary
                head = p.read_bytes()[:8192]
                if b"\x00" in head:
                    return (str(p), "", False, 0, True)
                txt = p.read_text(encoding="utf-8", errors="ignore")
                raw_len = p.stat().st_size
                was_trunc = False
                if max_chars_per_file is not None and len(txt) > max_chars_per_file:
                    txt = txt[:max_chars_per_file]
                    was_trunc = True
                return (str(p), txt, was_trunc, raw_len, False)
            except Exception as e:
                return (str(p), f"[Error reading file: {e}]", False, 0, False)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for path_str, txt, was_trunc, raw_len, is_bin in executor.map(_read_single, file_list):
                if is_bin:
                    skipped_binary.append(path_str)
                    continue
                if total_bytes + raw_len > budget and contents:
                    budget_exceeded = True
                    break
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
            "full_content": max_chars_per_file is None and not budget_exceeded,
            "max_chars_per_file": max_chars_per_file,
            "max_total_bytes": budget,
            "max_workers": workers,
            "truncated_files": truncated_files,
            "truncated_file_listing": truncated_listing,
            "total_bytes_on_disk": total_bytes,
            "budget_exceeded": budget_exceeded,
            "skipped_binary": skipped_binary[:50],
            "truncated": budget_exceeded or truncated_listing or bool(truncated_files),
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



