"""Code intelligence helpers: blast radius, failing slice parsing, edit safety checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from godkiller_mcp.schema import EvidenceType

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

# Engines live in godkiller_mcp.engines.* — re-export for stable import paths.
from godkiller_mcp.engines import (  # noqa: E402
    AstGrepEngine,
    AutoFixEngine,
    AutoSkillifyEngine,
    ContextPreviewEngine,
    CouncilDebateEngine,
    DeepScrapeEngine,
    EpistemicConfidenceGate,
    ExhaustiveReaderEngine,
    FastFindEngine,
    HyperSearchEngine,
    LogTraceEngine,
    PipelineRunner,
    RepoMapGenerator,
    SecurityScanEngine,
    SelfHealingEngine,
    Tag,
    _default_tools_dir,
    _find_dev_binary,
)
