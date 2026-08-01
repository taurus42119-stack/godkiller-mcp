"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.engines.search import _find_dev_binary


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



