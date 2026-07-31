"""Hollow-surface gate — reject unfinished / placeholder Python before claim_done.

Original GODKILLER module. Scans AST + marker tokens on disk.
Fail-closed: findings block claim unless GODKILLER_DEV_RELAX=1.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


_SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".godkiller",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

_MARKER_RE = re.compile(
    r"\b(TODO|FIXME|XXX|HACK)\b|"
    r"NotImplementedError|"
    r"#\s*(stub|placeholder|mock\b)|"
    r"raise\s+NotImplementedError|"
    r"\bcoming\s+soon\b|"
    r"\blorem\s+ipsum\b|"
    r"\bplaceholder\b|"
    r"\bmockup\b|"
    r"\bWIP\b|"
    r"\bTBD\b|"
    r"not\s+implemented|"
    r"pass\s*#\s*todo",
    re.IGNORECASE,
)

# Front-end / copy hollow signals (scanned in non-Python sources)
_WEB_HOLLOW_RE = re.compile(
    r"\b(TODO|FIXME|XXX|HACK|WIP|TBD)\b|"
    r"coming\s+soon|"
    r"lorem\s+ipsum|"
    r"placeholder|"
    r"mock[\s_-]?up|"
    r"under\s+construction|"
    r"replace\s+me|"
    r"your\s+(text|title|content)\s+here|"
    r"sample\s+data|"
    r"dummy\s+(text|data|content)|"
    r"not\s+implemented|"
    r"throw\s+new\s+Error\s*\(\s*['\"]not implemented|"
    r"TODO:\s*implement",
    re.IGNORECASE,
)

_WEB_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".css", ".scss", ".html", ".mdx"}


_ABSTRACT_DECOS = {"abstractmethod", "overload", "abc.abstractmethod"}


@dataclass
class HollowFinding:
    path: str
    line: int
    kind: str
    detail: str


@dataclass
class HollowReport:
    findings: List[HollowFinding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def clean(self) -> bool:
        return not self.findings

    def to_payload(self) -> dict:
        return {
            "source": "hollow_surface",
            "server_authored": True,
            "clean": self.clean,
            "files_scanned": self.files_scanned,
            "findings": [
                {"path": f.path, "line": f.line, "kind": f.kind, "detail": f.detail}
                for f in self.findings[:100]
            ],
            "summary": (
                "hollow_surface CLEAN"
                if self.clean
                else f"hollow_surface BLOCKED: {len(self.findings)} finding(s)"
            ),
        }


def _decorator_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for dec in getattr(node, "decorator_list", []) or []:
        if isinstance(dec, ast.Name):
            names.add(dec.id)
        elif isinstance(dec, ast.Attribute):
            parts = [dec.attr]
            cur = dec.value
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            names.add(".".join(reversed(parts)))
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                names.add(dec.func.id)
            elif isinstance(dec.func, ast.Attribute):
                names.add(dec.func.attr)
    return names


def _body_hollow(body: list[ast.stmt]) -> Optional[str]:
    real = body
    if (
        real
        and isinstance(real[0], ast.Expr)
        and isinstance(real[0].value, ast.Constant)
        and isinstance(real[0].value.value, str)
    ):
        real = real[1:]
    if not real:
        return "docstring_only"
    if len(real) != 1:
        return None
    stmt = real[0]
    if isinstance(stmt, ast.Pass):
        return "pass"
    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and stmt.value.value is Ellipsis:
        return "ellipsis"
    if isinstance(stmt, ast.Return):
        if stmt.value is None:
            return "bare_return"
        if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
            return "return_none"
    if isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Call):
        fn = stmt.exc.func
        if isinstance(fn, ast.Name) and fn.id == "NotImplementedError":
            return "not_implemented"
    return None


def _scan_python_source(path: Path, text: str) -> List[HollowFinding]:
    findings: List[HollowFinding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _MARKER_RE.search(line):
            findings.append(
                HollowFinding(str(path), i, "marker", line.strip()[:120])
            )
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _decorator_names(node) & _ABSTRACT_DECOS:
            continue
        tag = _body_hollow(node.body)
        if tag:
            findings.append(
                HollowFinding(
                    str(path),
                    getattr(node, "lineno", 1),
                    "hollow_body",
                    f"{node.name}:{tag}",
                )
            )
    return findings


def iter_code_files(roots: Sequence[Path], *, max_files: int = 200) -> Iterable[Path]:
    n = 0
    for root in roots:
        root = root.resolve()
        if root.is_file() and (
            root.suffix == ".py" or root.suffix.lower() in _WEB_SUFFIXES
        ):
            yield root
            n += 1
            if n >= max_files:
                return
            continue
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            suf = p.suffix.lower()
            if suf == ".py" or suf in _WEB_SUFFIXES:
                yield p
                n += 1
                if n >= max_files:
                    return


def _scan_web_source(path: Path, text: str) -> List[HollowFinding]:
    findings: List[HollowFinding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _WEB_HOLLOW_RE.search(line):
            findings.append(
                HollowFinding(str(path), i, "web_placeholder", line.strip()[:120])
            )
    return findings


def iter_py_files(roots: Sequence[Path], *, max_files: int = 200) -> Iterable[Path]:
    """Backward-compatible: Python-only iterator."""
    for p in iter_code_files(roots, max_files=max_files):
        if p.suffix == ".py":
            yield p


def scan_hollow_surface(
    roots: Sequence[str | Path],
    *,
    max_files: int = 200,
) -> HollowReport:
    report = HollowReport()
    paths = list(iter_code_files([Path(r) for r in roots], max_files=max_files))
    report.files_scanned = len(paths)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if path.suffix == ".py":
            report.findings.extend(_scan_python_source(path, text))
        else:
            report.findings.extend(_scan_web_source(path, text))
    return report


def paths_touched_in_state(state) -> List[str]:
    """Collect paths from blast / edit_safe / verify payloads."""
    out: List[str] = []
    for ev in getattr(state, "evidences", []) or []:
        payload = ev.payload or {}
        for key in ("path", "safe_path", "file", "target"):
            v = payload.get(key)
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        for key in ("paths", "files", "touched", "changed_files"):
            v = payload.get(key)
            if isinstance(v, list):
                out.extend(str(x) for x in v if x)
    # dedupe preserve order
    seen = set()
    uniq = []
    for p in out:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def claim_hollow_gate(
    state,
    *,
    workspace: str | Path | None = None,
    extra_roots: Optional[Sequence[str | Path]] = None,
) -> tuple[bool, str, HollowReport]:
    """
    Gate for claim_done. Scans touched paths; if none, scans workspace shallowly
    only when extra_roots/workspace provided. Empty scan roots → pass with note
    (verify_bundle still required elsewhere).
    """
    from godkiller_mcp.ship_mode import relax_enabled

    if relax_enabled():
        empty = HollowReport()
        return True, "hollow_surface skipped (GODKILLER_DEV_RELAX)", empty

    roots: List[Path] = []
    for p in paths_touched_in_state(state):
        roots.append(Path(p))
    if extra_roots:
        roots.extend(Path(r) for r in extra_roots)
    if not roots and workspace:
        ws = Path(workspace)
        roots.extend(sorted(ws.glob("*.py"))[:40])
        for pat in ("*.ts", "*.tsx", "*.js", "*.jsx", "*.vue", "*.css", "*.html"):
            roots.extend(sorted(ws.glob(pat))[:20])

    if not roots:
        # Vacuous pass was a critic hole — IDE-only edits never list paths
        kind = getattr(getattr(state, "handle", None), "kind", None)
        kind_v = getattr(kind, "value", str(kind or ""))
        if kind_v in ("bugfix", "refactor", "feature"):
            empty = HollowReport()
            return (
                False,
                "hollow_surface: no edit paths recorded — use blast_radius/edit_safe "
                "or pass workspace; cannot claim with empty scan on code tasks",
                empty,
            )
        empty = HollowReport()
        return True, "hollow_surface: no paths to scan", empty

    # Resolve relative paths against workspace when needed
    resolved = []
    ws = Path(workspace).resolve() if workspace else Path.cwd()
    for r in roots:
        if r.is_absolute():
            resolved.append(r)
        else:
            resolved.append((ws / r).resolve())

    report = scan_hollow_surface(resolved)
    if report.clean:
        return True, report.to_payload()["summary"], report
    sample = "; ".join(f"{f.path}:{f.line}:{f.kind}" for f in report.findings[:5])
    return (
        False,
        f"Forced gate: hollow_surface blocked claim_done — {sample}",
        report,
    )
