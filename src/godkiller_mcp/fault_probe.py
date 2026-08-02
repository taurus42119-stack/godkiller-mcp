"""Fault probe — diff-scoped mutation pressure (GODKILLER-native, deeper than v1).

Mutants run under a disposable shadow copy of the workspace so SIGKILL cannot
leave live-tree mutants. Legacy in-place unclean markers are still restored/blocked.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from godkiller_mcp.safe_exec import run_command_safely


def _probe_dirs(workspace: Path) -> Tuple[Path, Path]:
    root = Path(workspace) / ".godkiller"
    backup = root / "probe_backup"
    unclean = root / "probe_unclean.json"
    backup.mkdir(parents=True, exist_ok=True)
    return backup, unclean


def _restore_probe_backups_unlocked(ws: Path) -> Dict[str, Any]:
    """Caller must hold ``probe.lock`` (or accept races).

    Fail-closed: unclean marker stays if any listed file lacks a readable bak.
    """
    from godkiller_mcp.evidence_store import atomic_write_text

    backup_root, unclean = _probe_dirs(ws)
    restored: List[str] = []
    errors: List[str] = []
    pending: List[str] = []
    if unclean.exists():
        try:
            meta = json.loads(unclean.read_text(encoding="utf-8"))
            pending = [str(r) for r in (meta.get("files") or [])]
            for rel in pending:
                bak = backup_root / f"{str(rel).replace('/', '__').replace(chr(92), '__')}.bak"
                target = ws / rel
                if bak.is_file():
                    atomic_write_text(target, bak.read_text(encoding="utf-8"))
                    restored.append(str(rel))
                    try:
                        bak.unlink()
                    except OSError:
                        pass
                else:
                    errors.append(f"missing_bak:{rel}")
        except Exception as exc:
            errors.append(str(exc))
    for bak in backup_root.glob("*.bak"):
        rel = bak.name[: -len(".bak")].replace("__", "/")
        if rel in restored:
            continue
        target = ws / rel
        try:
            atomic_write_text(target, bak.read_text(encoding="utf-8"))
            restored.append(rel)
            bak.unlink(missing_ok=True)
            if rel in pending and f"missing_bak:{rel}" in errors:
                errors = [e for e in errors if e != f"missing_bak:{rel}"]
        except Exception as exc:
            errors.append(f"{rel}:{exc}")
    # Only clear unclean when every listed file was restored and no errors remain
    still_pending = [r for r in pending if r not in restored]
    if unclean.exists() and not errors and not still_pending:
        try:
            unclean.unlink()
        except OSError:
            pass
    return {
        "restored": restored,
        "errors": errors,
        "pending": still_pending,
        "clean": not unclean.exists(),
    }


def restore_probe_backups(workspace: Path | str) -> Dict[str, Any]:
    """Restore any leftover mutant files from .godkiller/probe_backup (crash recovery)."""
    from godkiller_mcp.file_lock import workspace_lock

    ws = Path(workspace).resolve()
    with workspace_lock(ws, name="probe.lock"):
        return _restore_probe_backups_unlocked(ws)


def probe_unclean(workspace: Path | str) -> bool:
    return (Path(workspace) / ".godkiller" / "probe_unclean.json").exists()


def warn_if_probe_unclean(workspace: Path | str, *, stream=None) -> bool:
    """Print a visible crash leftover warning. Returns True if unclean marker present."""
    import sys

    ws = Path(workspace).resolve()
    if not probe_unclean(ws):
        return False
    out = stream if stream is not None else sys.stderr
    msg = (
        f"WARNING: fault_probe unclean marker at {ws / '.godkiller' / 'probe_unclean.json'} — "
        "workspace may still contain mutants from a prior SIGKILL/crash. "
        "Run: godkiller-restore --workspace .   (or claim_done will attempt restore)"
    )
    try:
        print(msg, file=out, flush=True)
    except OSError:
        pass
    return True


def _probe_ignore_names() -> set[str]:
    return {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".godkiller",
        "dist",
        "build",
        ".eggs",
        "htmlcov",
        "coverage",
    }


def _copy_workspace_shadow(src: Path, dst: Path) -> None:
    """Copy workspace into a disposable shadow (mutation target). Never write mutants to src."""
    import shutil

    ignore = _probe_ignore_names()

    def _ignore(dirpath: str, names: list[str]) -> set[str]:
        skipped = set()
        for n in names:
            if n in ignore or n.endswith(".pyc") or n.endswith(".pyo"):
                skipped.add(n)
        return skipped

    shutil.copytree(src, dst, ignore=_ignore, symlinks=False)


def _run_mutant_in_shadow(
    *,
    workspace: Path,
    rel: str,
    mutated: str,
    test_command: str,
    timeout_sec: int,
) -> Any:
    """Apply mutant only under a temp shadow copy; original workspace file untouched."""
    import tempfile

    from godkiller_mcp.evidence_store import atomic_write_text

    with tempfile.TemporaryDirectory(prefix="gk_fp_") as td:
        shadow = Path(td) / "ws"
        _copy_workspace_shadow(workspace, shadow)
        target = shadow / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, mutated)
        return run_command_safely(test_command, cwd=shadow, timeout_sec=timeout_sec)


def require_probe_clean_or_restore(workspace: Path | str | None = None) -> Optional[Dict[str, Any]]:
    """Return error payload if unclean after restore attempt; else None.

    Used by dispatch to block facades until mutants from a prior crash are cleared.
    """
    try:
        from godkiller_mcp.path_sandbox import WorkspaceRootError, workspace_root

        ws = Path(workspace).resolve() if workspace else workspace_root()
    except WorkspaceRootError:
        ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    except Exception:
        ws = Path(workspace).resolve() if workspace else Path.cwd().resolve()

    if not probe_unclean(ws):
        return None
    warn_if_probe_unclean(ws)
    info = restore_probe_backups(ws)
    if not probe_unclean(ws):
        return None
    return {
        "ok": False,
        "error": "probe_unclean",
        "detail": (
            "prior fault_probe crash left mutants; restore incomplete — "
            "run godkiller-restore --workspace <root> then retry"
        ),
        "restored": info.get("restored"),
        "errors": info.get("errors"),
        "workspace": str(ws),
        "fix": "godkiller-restore --workspace .",
    }


# Tools allowed while unclean (status / restore path / probe itself to re-attempt).
PROBE_UNCLEAN_ALLOW = frozenset(
    {
        "gk_honesty_status",
        "fault_probe",
        "exit_checklist",
        "ledger_tail",
    }
)


@dataclass
class FaultProbeReport:
    clean: bool
    mutants_tried: int = 0
    killed: int = 0
    survivors: List[Dict[str, Any]] = field(default_factory=list)
    skipped_reason: str = ""
    targets: List[str] = field(default_factory=list)
    test_command: str = ""
    summary: str = ""
    material_hash: str = ""
    scope: str = ""
    complete: bool = True

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source": "fault_probe",
            "server_authored": True,
            "clean": self.clean,
            "mutants_tried": self.mutants_tried,
            "killed": self.killed,
            "survivors": self.survivors[:40],
            "skipped_reason": self.skipped_reason,
            "targets": self.targets,
            "target": self.targets[0] if self.targets else "",
            "test_command": self.test_command,
            "material_hash": self.material_hash,
            "material_scope": "workspace",
            "complete": self.complete,
            "scope": self.scope,
            "summary": self.summary
            or (
                "fault_probe CLEAN"
                if self.clean
                else f"fault_probe SURVIVORS={len(self.survivors)}"
            ),
        }


def _flip_compare(op: ast.cmpop) -> Optional[ast.cmpop]:
    table = {
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
        ast.Lt: ast.GtE,
        ast.Gt: ast.LtE,
        ast.LtE: ast.Gt,
        ast.GtE: ast.Lt,
        ast.Is: ast.IsNot,
        ast.IsNot: ast.Is,
        ast.In: ast.NotIn,
        ast.NotIn: ast.In,
    }
    for src, dst in table.items():
        if isinstance(op, src):
            return dst()
    return None


def _flip_binop(op: ast.operator) -> Optional[ast.operator]:
    table = {
        ast.Add: ast.Sub,
        ast.Sub: ast.Add,
        ast.Mult: ast.Div,
        ast.Div: ast.Mult,
        ast.BitOr: ast.BitAnd,
        ast.BitAnd: ast.BitOr,
    }
    for src, dst in table.items():
        if isinstance(op, src):
            return dst()
    return None


def _generate_mutants(src: str, *, max_per_file: int = 8) -> List[Tuple[str, str, str]]:
    """Generate up to max_per_file single-site mutants (all sites, not only first)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    sites: List[Tuple[str, str, ast.AST]] = []

    class Finder(ast.NodeVisitor):
        def visit_Compare(self, node: ast.Compare):
            if node.ops and _flip_compare(node.ops[0]) is not None:
                sites.append(("compare_flip", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

        def visit_BinOp(self, node: ast.BinOp):
            if _flip_binop(node.op) is not None:
                sites.append(("binop_flip", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

        def visit_Return(self, node: ast.Return):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                sites.append(("bool_return_flip", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

        def visit_Constant(self, node: ast.Constant):
            if isinstance(node.value, bool):
                return  # handled via Return bool flip
            if isinstance(node.value, int) and node.value in (0, 1, -1, 2):
                sites.append(("int_const_flip", f"line {getattr(node, 'lineno', '?')}", node))
            if isinstance(node.value, str) and node.value == "":
                sites.append(("empty_str_to_x", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id in ("True", "False"):
                sites.append(("name_bool_flip", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

        def visit_UnaryOp(self, node: ast.UnaryOp):
            if isinstance(node.op, ast.Not):
                sites.append(("drop_not", f"line {getattr(node, 'lineno', '?')}", node))
            self.generic_visit(node)

    Finder().visit(tree)
    out: List[Tuple[str, str, str]] = []
    for kind, detail, target_node in sites[:max_per_file]:
        try:
            fresh = ast.parse(src)
        except SyntaxError:
            break

        class Applier(ast.NodeTransformer):
            def __init__(self):
                self.done = False

            def visit_Compare(self, node: ast.Compare):
                node = self.generic_visit(node)
                if self.done or kind != "compare_flip":
                    return node
                if getattr(node, "lineno", None) == getattr(target_node, "lineno", None) and node.ops:
                    flipped = _flip_compare(node.ops[0])
                    if flipped is not None:
                        node.ops[0] = flipped
                        self.done = True
                return node

            def visit_BinOp(self, node: ast.BinOp):
                node = self.generic_visit(node)
                if self.done or kind != "binop_flip":
                    return node
                if getattr(node, "lineno", None) == getattr(target_node, "lineno", None):
                    flipped = _flip_binop(node.op)
                    if flipped is not None:
                        node.op = flipped
                        self.done = True
                return node

            def visit_Return(self, node: ast.Return):
                node = self.generic_visit(node)
                if self.done or kind != "bool_return_flip":
                    return node
                if getattr(node, "lineno", None) == getattr(target_node, "lineno", None):
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                        node.value = ast.Constant(value=not node.value.value)
                        self.done = True
                return node

            def visit_Constant(self, node: ast.Constant):
                node = self.generic_visit(node)
                if self.done:
                    return node
                if kind == "int_const_flip" and isinstance(node.value, int):
                    if getattr(node, "lineno", None) == getattr(target_node, "lineno", None):
                        node.value = {0: 1, 1: 0, -1: 1, 2: 3}.get(node.value, node.value + 1)
                        self.done = True
                if kind == "empty_str_to_x" and node.value == "":
                    if getattr(node, "lineno", None) == getattr(target_node, "lineno", None):
                        node.value = "x"
                        self.done = True
                return node

            def visit_Name(self, node: ast.Name):
                node = self.generic_visit(node)
                if self.done or kind != "name_bool_flip":
                    return node
                if getattr(node, "lineno", None) == getattr(target_node, "lineno", None):
                    if node.id == "True":
                        return ast.Name(id="False", ctx=node.ctx)
                    if node.id == "False":
                        return ast.Name(id="True", ctx=node.ctx)
                return node

            def visit_UnaryOp(self, node: ast.UnaryOp):
                node = self.generic_visit(node)
                if self.done or kind != "drop_not":
                    return node
                if getattr(node, "lineno", None) == getattr(target_node, "lineno", None) and isinstance(
                    node.op, ast.Not
                ):
                    self.done = True
                    return node.operand
                return node

        applier = Applier()
        new_tree = applier.visit(fresh)
        if not applier.done:
            continue
        ast.fix_missing_locations(new_tree)
        try:
            text = ast.unparse(new_tree)
        except Exception:
            continue
        out.append((kind, detail, text))
    return out


def git_changed_py_files(workspace: Path) -> List[Path]:
    """Diff-scoped targets: staged + unstaged + untracked .py under workspace."""
    files: List[Path] = []
    try:
        cmds = [
            ["git", "diff", "--name-only", "--diff-filter=ACMR"],
            ["git", "diff", "--name-only", "--cached", "--diff-filter=ACMR"],
            ["git", "ls-files", "--others", "--exclude-standard"],
        ]
        seen = set()
        for cmd in cmds:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                continue
            for line in proc.stdout.splitlines():
                line = line.strip()
                if not line.endswith(".py"):
                    continue
                p = (workspace / line).resolve()
                if p.is_file() and str(p) not in seen:
                    seen.add(str(p))
                    files.append(p)
    except (OSError, subprocess.SubprocessError):
        return []
    return files


def _is_under_workspace(path: Path, workspace: Path) -> bool:
    try:
        path.resolve().relative_to(workspace.resolve())
        return True
    except ValueError:
        return False


def resolve_probe_targets(
    workspace: Path,
    *,
    target: Optional[str | Path] = None,
    targets: Optional[Sequence[str | Path]] = None,
) -> Tuple[List[Path], str]:
    workspace = workspace.resolve()

    def _accept(p: Path) -> Optional[Path]:
        p = p.resolve()
        if not _is_under_workspace(p, workspace):
            return None
        if p.is_file() and p.suffix == ".py":
            return p
        return None

    if targets:
        out = []
        for t in targets:
            p = Path(t)
            if not p.is_absolute():
                p = (workspace / p)
            acc = _accept(p)
            if acc is not None:
                out.append(acc)
        return out, "explicit_targets"
    if target:
        p = Path(target)
        if not p.is_absolute():
            p = workspace / p
        acc = _accept(p)
        if acc is not None:
            return [acc], "explicit_target"
        return [], "target_outside_workspace"
    changed = git_changed_py_files(workspace)
    if changed:
        return [c for c in changed[:12] if _is_under_workspace(c, workspace)], "git_diff_scoped"
    return [], "no_targets"


def run_fault_probe(
    *,
    workspace: str | Path,
    target_file: str | Path | None = None,
    targets: Optional[Sequence[str | Path]] = None,
    test_command: str = "python -m pytest -q --tb=no",
    timeout_sec: int = 45,
    max_mutants: int = 24,
    max_per_file: int = 12,
) -> FaultProbeReport:
    from godkiller_mcp.freshness import hash_workspace_code
    from godkiller_mcp.verify_bundle import detect_hacking, is_test_verify_command

    workspace = Path(workspace).resolve()

    # Same allowlist + workspace path gate as verify_bundle
    blocked, why = detect_hacking(test_command, cwd=workspace)
    if blocked:
        return FaultProbeReport(
            clean=False,
            skipped_reason=f"test_command blocked: {why}",
            test_command=test_command,
            summary="fault_probe BLOCKED: illegal test_command",
        )
    if not is_test_verify_command(test_command):
        return FaultProbeReport(
            clean=False,
            skipped_reason="test_command must be pytest/unittest (lint-only not allowed)",
            test_command=test_command,
            summary="fault_probe BLOCKED: test_command not claim-grade",
        )

    files, scope = resolve_probe_targets(
        workspace, target=target_file, targets=targets
    )
    if not files:
        return FaultProbeReport(
            clean=False,
            skipped_reason="no python targets inside workspace (pass target= or edit files under git)",
            scope=scope,
            summary="fault_probe SKIP: no targets",
        )

    # B3: bind to full workspace tree, not decoy target list
    mat = hash_workspace_code(workspace)
    if not mat.get("complete", True):
        return FaultProbeReport(
            clean=False,
            skipped_reason="workspace material_hash incomplete — too many code files",
            targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
            test_command=test_command,
            material_hash=mat["material_hash"],
            scope=scope,
            complete=bool(mat.get("complete", True)),
            summary="fault_probe BLOCKED: incomplete workspace hash",
        )

    base = run_command_safely(test_command, cwd=workspace, timeout_sec=timeout_sec)
    if base.returncode != 0:
        return FaultProbeReport(
            clean=False,
            mutants_tried=0,
            skipped_reason="baseline tests already failing — fix verify_bundle first",
            targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
            test_command=test_command,
            material_hash=mat["material_hash"],
            scope=scope,
            complete=bool(mat.get("complete", True)),
            summary="fault_probe BLOCKED: baseline red",
        )

    survivors: List[Dict[str, Any]] = []
    killed = 0
    tried = 0
    budget = max_mutants

    from godkiller_mcp.file_lock import workspace_lock

    with workspace_lock(workspace, name="probe.lock", timeout_sec=max(60.0, timeout_sec * 3)):
        # Crash recovery from prior *legacy* in-place unclean probe
        warn_if_probe_unclean(workspace)
        _restore_probe_backups_unlocked(Path(workspace).resolve())
        if probe_unclean(workspace):
            return FaultProbeReport(
                clean=False,
                skipped_reason="probe_unclean leftover — restore failed; fix files under .godkiller/probe_backup",
                targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
                test_command=test_command,
                material_hash=mat["material_hash"],
                scope=scope,
                complete=bool(mat.get("complete", True)),
                summary="fault_probe BLOCKED: unclean workspace after prior crash",
            )

        # Mutants apply only under a disposable shadow copy — workspace files stay pristine
        # even on SIGKILL mid-test (no in-place write → no probe_unclean for this path).
        for fpath in files:
            if tried >= budget:
                break
            if not _is_under_workspace(fpath, workspace):
                continue
            try:
                original = fpath.read_text(encoding="utf-8")
            except OSError:
                continue
            mutants = _generate_mutants(original, max_per_file=max_per_file)
            for kind, detail, mutated in mutants:
                if tried >= budget:
                    break
                tried += 1
                rel = str(fpath.relative_to(workspace)).replace("\\", "/")
                proc = _run_mutant_in_shadow(
                    workspace=workspace,
                    rel=rel,
                    mutated=mutated,
                    test_command=test_command,
                    timeout_sec=timeout_sec,
                )
                entry = {
                    "file": rel,
                    "kind": kind,
                    "detail": detail,
                    "exit_code": proc.returncode,
                    "digest": hashlib.sha256(mutated.encode()).hexdigest()[:16],
                    "shadow": True,
                }
                if proc.returncode == 0:
                    survivors.append(entry)
                else:
                    killed += 1

                # Integrity: original must still match pre-mutant bytes
                try:
                    if fpath.read_text(encoding="utf-8") != original:
                        return FaultProbeReport(
                            clean=False,
                            mutants_tried=tried,
                            killed=killed,
                            survivors=survivors,
                            targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
                            test_command=test_command,
                            material_hash=mat["material_hash"],
                            scope=scope,
                            complete=bool(mat.get("complete", True)),
                            summary="fault_probe ABORT: workspace file changed during shadow probe",
                            skipped_reason=f"shadow integrity failed for {rel}",
                        )
                except OSError:
                    pass

    clean = tried > 0 and len(survivors) == 0
    if tried == 0:
        return FaultProbeReport(
            clean=False,
            mutants_tried=0,
            killed=0,
            survivors=[],
            targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
            test_command=test_command,
            material_hash=mat["material_hash"],
            scope=scope,
            complete=bool(mat.get("complete", True)),
            summary="fault_probe CLEAN (no mutant sites)",
            skipped_reason="no applicable mutant sites in scoped files",
        )

    return FaultProbeReport(
        clean=clean,
        mutants_tried=tried,
        killed=killed,
        survivors=survivors,
        targets=[str(f.relative_to(workspace)).replace("\\", "/") for f in files],
        test_command=test_command,
        material_hash=mat["material_hash"],
        scope=scope,
        complete=bool(mat.get("complete", True)),
        summary=(
            f"fault_probe CLEAN — killed {killed}/{tried} ({scope})"
            if clean
            else f"fault_probe FAIL — {len(survivors)} survivor(s) in {scope}; tests too shallow"
        ),
    )


def claim_fault_probe_gate(state, *, workspace: Optional[str] = None) -> Tuple[bool, str]:
    from godkiller_mcp.ship_mode import env_disables, relax_enabled

    if relax_enabled():
        return True, "fault_probe skipped (GODKILLER_DEV_RELAX)"
    if env_disables("GODKILLER_FAULT_PROBE"):
        return True, "fault_probe disabled (relax only)"

    ws = Path(workspace) if workspace else Path.cwd()
    if probe_unclean(ws):
        info = restore_probe_backups(ws)
        if probe_unclean(ws):
            return (
                False,
                "fault_probe UNCLEAN — prior probe crash left mutants; "
                f"restored={info.get('restored')} errors={info.get('errors')} "
                "— fix .godkiller/probe_backup then re-run fault_probe",
            )

    from godkiller_mcp.freshness import hash_workspace_code
    from godkiller_mcp.hollow_surface import paths_touched_in_state

    paths = [p for p in paths_touched_in_state(state) if str(p).endswith(".py")]
    if not paths:
        kind = getattr(getattr(state, "handle", None), "kind", None)
        kind_v = getattr(kind, "value", str(kind or ""))
        if kind_v in ("bugfix", "refactor", "feature"):
            return (
                False,
                "fault_probe: no python edit paths — record edits via blast/edit_safe "
                "or run fault_probe(targets=...) before claim",
            )
        return True, "fault_probe: no python edit paths"

    for ev in getattr(state, "evidences", []) or []:
        payload = ev.payload or {}
        if (
            payload.get("source") == "fault_probe"
            and payload.get("server_authored") is True
            and payload.get("clean") is True
        ):
            tried = int(payload.get("mutants_tried") or 0)
            if tried <= 0:
                return (
                    False,
                    "fault_probe inconclusive (0 mutants tried) — not claim-grade; "
                    "deepen assertions or expand targets",
                )
            recorded = payload.get("material_hash")
            if not recorded:
                return False, "fault_probe missing material_hash — rerun probe"
            if payload.get("complete") is False:
                return False, "fault_probe material_hash incomplete — rerun probe"
            # B3: always rehash full workspace — decoy targets cannot hide edits
            live = hash_workspace_code(ws)
            if not live.get("complete", True):
                return False, "workspace hash incomplete — cannot validate probe freshness"
            if live["material_hash"] != recorded:
                return (
                    False,
                    "stale fault_probe: workspace changed after probe — rerun gk_verify.probe",
                )
            return True, "fault_probe clean + fresh (workspace)"
    return (
        False,
        "Forced gate: fault_probe clean evidence required after python edits "
        "(gk_verify action=probe, diff-scoped).",
    )
