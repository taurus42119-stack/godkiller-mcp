"""Fault probe — kill weak tests by injecting simple mutants (GODKILLER-native).

Inspired by mutation-testing practice, not a third-party product port.
If a mutant still passes the suite, claim_done must not trust that suite.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from godkiller_mcp.safe_exec import run_command_safely


@dataclass
class Mutant:
    kind: str
    detail: str
    source_hash: str


@dataclass
class FaultProbeReport:
    clean: bool
    mutants_tried: int = 0
    killed: int = 0
    survivors: List[Dict[str, Any]] = field(default_factory=list)
    skipped_reason: str = ""
    target: str = ""
    test_command: str = ""
    summary: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source": "fault_probe",
            "server_authored": True,
            "clean": self.clean,
            "mutants_tried": self.mutants_tried,
            "killed": self.killed,
            "survivors": self.survivors[:20],
            "skipped_reason": self.skipped_reason,
            "target": self.target,
            "test_command": self.test_command,
            "summary": self.summary
            or (
                "fault_probe CLEAN"
                if self.clean
                else f"fault_probe SURVIVORS={len(self.survivors)}"
            ),
        }


class _MutateCompare(ast.NodeTransformer):
    """Flip first Compare op (== <-> !=, < <-> >=, etc.)."""

    def __init__(self):
        self.done = False
        self.detail = ""

    def visit_Compare(self, node: ast.Compare):
        self.generic_visit(node)
        if self.done or not node.ops:
            return node
        op = node.ops[0]
        repl = None
        if isinstance(op, ast.Eq):
            repl = ast.NotEq()
            self.detail = "== -> !="
        elif isinstance(op, ast.NotEq):
            repl = ast.Eq()
            self.detail = "!= -> =="
        elif isinstance(op, ast.Lt):
            repl = ast.GtE()
            self.detail = "< -> >="
        elif isinstance(op, ast.Gt):
            repl = ast.LtE()
            self.detail = "> -> <="
        if repl is None:
            return node
        node.ops[0] = repl
        self.done = True
        return node


class _MutateBinOp(ast.NodeTransformer):
    def __init__(self):
        self.done = False
        self.detail = ""

    def visit_BinOp(self, node: ast.BinOp):
        self.generic_visit(node)
        if self.done:
            return node
        if isinstance(node.op, ast.Add):
            node.op = ast.Sub()
            self.detail = "+ -> -"
            self.done = True
        elif isinstance(node.op, ast.Sub):
            node.op = ast.Add()
            self.detail = "- -> +"
            self.done = True
        elif isinstance(node.op, ast.Mult):
            node.op = ast.Div()
            self.detail = "* -> /"
            self.done = True
        return node


class _MutateReturnTrue(ast.NodeTransformer):
    def __init__(self):
        self.done = False
        self.detail = ""

    def visit_Return(self, node: ast.Return):
        self.generic_visit(node)
        if self.done:
            return node
        if isinstance(node.value, ast.Constant) and node.value.value is True:
            node.value = ast.Constant(value=False)
            self.detail = "return True -> False"
            self.done = True
        elif isinstance(node.value, ast.Constant) and node.value.value is False:
            node.value = ast.Constant(value=True)
            self.detail = "return False -> True"
            self.done = True
        return node


def _apply_mutators(src: str) -> List[Tuple[str, str, str]]:
    """Return list of (kind, detail, mutated_source)."""
    out: List[Tuple[str, str, str]] = []
    for kind, cls in (
        ("compare_flip", _MutateCompare),
        ("binop_flip", _MutateBinOp),
        ("bool_return_flip", _MutateReturnTrue),
    ):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return out
        mut = cls()
        new_tree = mut.visit(tree)
        if not mut.done:
            continue
        ast.fix_missing_locations(new_tree)
        try:
            text = ast.unparse(new_tree)
        except Exception:
            continue
        out.append((kind, mut.detail, text))
    return out


def run_fault_probe(
    *,
    workspace: str | Path,
    target_file: str | Path,
    test_command: str = "python -m pytest -q --tb=no",
    timeout_sec: int = 45,
    max_mutants: int = 3,
) -> FaultProbeReport:
    workspace = Path(workspace).resolve()
    target = Path(target_file)
    if not target.is_absolute():
        target = (workspace / target).resolve()
    if not target.is_file() or target.suffix != ".py":
        return FaultProbeReport(
            clean=False,
            skipped_reason=f"target not a python file: {target}",
            target=str(target),
            summary="fault_probe SKIP: bad target",
        )
    try:
        original = target.read_text(encoding="utf-8")
    except OSError as exc:
        return FaultProbeReport(
            clean=False,
            skipped_reason=str(exc),
            target=str(target),
            summary="fault_probe SKIP: read error",
        )

    mutants = _apply_mutators(original)[:max_mutants]
    if not mutants:
        return FaultProbeReport(
            clean=True,
            mutants_tried=0,
            skipped_reason="no applicable mutants in file",
            target=str(target),
            test_command=test_command,
            summary="fault_probe CLEAN (no mutants applicable)",
        )

    # Baseline must pass first
    base = run_command_safely(test_command, cwd=workspace, timeout_sec=timeout_sec)
    if base.returncode != 0:
        return FaultProbeReport(
            clean=False,
            mutants_tried=0,
            skipped_reason="baseline tests already failing — fix verify_bundle first",
            target=str(target),
            test_command=test_command,
            summary="fault_probe BLOCKED: baseline red",
        )

    survivors: List[Dict[str, Any]] = []
    killed = 0
    backup = original
    try:
        for kind, detail, mutated in mutants:
            target.write_text(mutated, encoding="utf-8")
            proc = run_command_safely(test_command, cwd=workspace, timeout_sec=timeout_sec)
            entry = {
                "kind": kind,
                "detail": detail,
                "exit_code": proc.returncode,
                "digest": hashlib.sha256(mutated.encode()).hexdigest()[:16],
            }
            if proc.returncode == 0:
                survivors.append(entry)
            else:
                killed += 1
    finally:
        target.write_text(backup, encoding="utf-8")

    clean = len(survivors) == 0
    return FaultProbeReport(
        clean=clean,
        mutants_tried=len(mutants),
        killed=killed,
        survivors=survivors,
        target=str(target),
        test_command=test_command,
        summary=(
            "fault_probe CLEAN — all mutants killed"
            if clean
            else f"fault_probe FAIL — {len(survivors)} survivor(s); tests too weak"
        ),
    )


def claim_fault_probe_gate(state, *, workspace: Optional[str] = None) -> Tuple[bool, str]:
    """Require a clean server-authored fault_probe evidence when paths were edited."""
    import os

    if os.environ.get("GODKILLER_DEV_RELAX", "").strip() == "1":
        return True, "fault_probe skipped (GODKILLER_DEV_RELAX)"
    if os.environ.get("GODKILLER_FAULT_PROBE", "1").strip() in ("0", "false", "off"):
        return True, "fault_probe disabled via GODKILLER_FAULT_PROBE=0"

    from godkiller_mcp.hollow_surface import paths_touched_in_state

    paths = [p for p in paths_touched_in_state(state) if str(p).endswith(".py")]
    if not paths:
        return True, "fault_probe: no python edit paths"

    for ev in getattr(state, "evidences", []) or []:
        payload = ev.payload or {}
        if (
            payload.get("source") == "fault_probe"
            and payload.get("server_authored") is True
            and payload.get("clean") is True
        ):
            return True, "fault_probe clean evidence present"

    return (
        False,
        "Forced gate: fault_probe clean evidence required after python edits "
        "(gk_verify action=probe). Survivors mean tests are too weak to claim_done.",
    )
