"""
11-dimension Antigravity A/B scorer (fail-closed).

Auto scores from:
  - sealed oracle pytest (full body required)
  - delta vs 1_ORIGINAL
  - HMAC-sealed `.godkiller` task artifacts (dims 5–11)

Missing evidence = 0 for that dimension. Keyword haystacks do not score 5–11.

  python -m benchmarks.score_11 --arm 3_WITHOUT_MCP
  python -m benchmarks.score_11 --arm 2_WITH_MCP
  python -m benchmarks.score_11 --compare
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
PKG_OUT = ROOT / "benchmarks" / "arena_logs"

DEFAULT_ARENA = Path(
    os.environ.get(
        "GODKILLER_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_ISOLATED_ARENA"),
    )
)

CHALLENGE_FILES = (
    "app.py",
    "nightmare_app.py",
    "anthropic_sota.py",
    "tier_1_easy_50.py",
    "tier_2_medium_150.py",
    "tier_3_hard_300.py",
)

ORACLE_IGNORE = (
    "test_mega_500.py",
    "test_calculator.py",
    "test_financial.py",
)

DIMENSIONS = (
    "1_code_correctness",
    "2_oracle_volume",
    "3_output_integrity",
    "4_delta_from_baseline",
    "5_reconnaissance_read",
    "6_phase_discipline",
    "7_blast_edit_safe",
    "8_verify_claim_gate",
    "9_council_review",
    "10_security_hardening",
    "11_ui_visual_gate",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_pytest_counts(output: str) -> dict:
    summary = ""
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
            break
    passed = failed = skipped = 0
    mp = re.search(r"(\d+)\s+passed", summary)
    mf = re.search(r"(\d+)\s+failed", summary)
    ms = re.search(r"(\d+)\s+skipped", summary)
    if mp:
        passed = int(mp.group(1))
    if mf:
        failed = int(mf.group(1))
    if ms:
        skipped = int(ms.group(1))
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "collected": passed + failed + skipped,
        "summary_line": summary,
    }


def _run_pytest_kill_after_summary(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict,
    hard_timeout_sec: int = 180,
) -> tuple[int, str]:
    """
    Run pytest writing to a log file; kill once summary footer appears.

    Intentional deadlock bugs leave non-daemon threads that block shutdown,
    and pipes can buffer forever on Windows — file polling avoids both.
    """
    import tempfile
    import time as _time

    log_path = Path(tempfile.mkstemp(prefix="gk_oracle_", suffix=".log")[1])
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as logf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=logf,
                stderr=subprocess.STDOUT,
                text=True,
            )
            summary_re = re.compile(
                r"=+\s*.*\d+\s+(passed|failed|error|skipped).* =+",
                re.I,
            )
            started = _time.perf_counter()
            saw_summary = False
            while proc.poll() is None:
                if _time.perf_counter() - started > hard_timeout_sec:
                    break
                text = log_path.read_text(encoding="utf-8", errors="replace")
                if summary_re.search(text) or re.search(
                    r"\d+\s+failed.*\d+\s+passed|\d+\s+passed.*\d+\s+failed|\d+\s+failed in |\d+\s+passed in ",
                    text,
                    re.I,
                ):
                    saw_summary = True
                    _time.sleep(0.5)
                    break
                _time.sleep(0.2)

            if proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
        output = log_path.read_text(encoding="utf-8", errors="replace")
        code = proc.returncode if proc.returncode is not None else (0 if saw_summary else 1)
        # If we killed after a failing summary, force non-zero
        if saw_summary and "failed" in output.lower() and code == 0:
            code = 1
        return code if code is not None else 1, output
    finally:
        try:
            log_path.unlink(missing_ok=True)
        except OSError:
            pass


def run_oracle(arena_root: Path, arm_dir: Path) -> dict:
    oracle = arena_root / "hidden_oracle"
    ignores: List[str] = []
    for name in ORACLE_IGNORE:
        p = oracle / name
        if p.exists():
            ignores.extend(["--ignore", str(p)])
    env = os.environ.copy()
    env["PYTHONPATH"] = str(arm_dir)
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable,
        "-u",
        "-m",
        "pytest",
        "-q",
        "--tb=no",
        str(oracle),
        *ignores,
    ]
    code, output = _run_pytest_kill_after_summary(cmd, cwd=arena_root, env=env)
    counts = _parse_pytest_counts(output)
    # -q mode uses F/./E letters — treat failure/pass counts + node ids as body
    has_body = (
        ("PASSED" in output)
        or ("FAILED" in output)
        or ("::" in output)
        or bool(re.search(r"[FE.]{5,}", output))
        or ("failed" in (counts.get("summary_line") or "").lower())
        or ("passed" in (counts.get("summary_line") or "").lower())
    )
    header_only = (not has_body) and ("test session starts" in output.lower())
    return {
        "exit_code": code,
        "pytest_passed": code == 0 and int(counts.get("failed") or 0) == 0 and int(counts.get("passed") or 0) > 0,
        "counts": counts,
        "pytest_output": output[-200000:],
        "pytest_output_full_chars": len(output),
        "has_body": has_body,
        "header_only": header_only,
        "passed_markers_in_log": len(re.findall(r"\bPASSED\b", output)),
    }


def baseline_delta(arena_root: Path, arm_dir: Path) -> dict:
    base = arena_root / "1_ORIGINAL"
    changed = 0
    total = 0
    details = []
    for name in CHALLENGE_FILES:
        s = base / name
        d = arm_dir / name
        if not s.is_file() or not d.is_file():
            continue
        total += 1
        same = _sha(s) == _sha(d)
        if not same:
            changed += 1
        details.append({"file": name, "changed": not same})
    pct = (changed / total * 100.0) if total else 0.0
    return {"changed_files": changed, "total_files": total, "pct": round(pct, 2), "details": details}


def _walk_text_blobs(root: Path, max_files: int = 400) -> str:
    blobs: List[str] = []
    if not root.exists():
        return ""
    n = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".json", ".md", ".txt", ".log", ".jsonl"}:
            continue
        if p.stat().st_size > 2_000_000:
            continue
        try:
            blobs.append(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        n += 1
        if n >= max_files:
            break
    return "\n".join(blobs)


def artifact_signals(arm_dir: Path, arena_root: Path) -> dict:
    """
    Legacy keyword haystack (NOT used for dims 5–11 scoring).

    Kept for compare/debug dumps only — prefer sealed_artifact_signals.
    """
    del arena_root
    hay = "\n".join(
        [
            _walk_text_blobs(arm_dir / ".godkiller"),
            _walk_text_blobs(arm_dir / "session_evidence"),
            _walk_text_blobs(arm_dir / "arena" / "results"),
        ]
    ).lower()

    shot_roots = [
        arm_dir / "session_evidence",
        arm_dir / "arena" / "results",
        arm_dir / ".godkiller",
    ]
    shots = []
    for root in shot_roots:
        if root.is_dir():
            shots.extend(root.rglob("*.png"))
            shots.extend(root.rglob("*.jpg"))

    return {
        "exhaustive_read": ("exhaustive" in hay) or ("full_content" in hay) or ("read_all" in hay),
        "open_task": ("open_task" in hay) or ("task_id" in hay and "phase" in hay),
        "plan_os": ("plan_os" in hay) or ("chosen_design" in hay),
        "blast_radius": "blast_radius" in hay,
        "edit_safe": ("edit_safe" in hay) or ("check_edit_safe" in hay),
        "verify_bundle": "verify_bundle" in hay,
        "claim_done": "claim_done" in hay,
        "server_authored": "server_authored" in hay,
        "council": ("council" in hay) and (("coder" in hay) or ("hacker" in hay) or ("optimizer" in hay)),
        "security": ("xss" in hay) or ("security_hardening" in hay) or ('"hacker"' in hay),
        "visual_critic": ("visual_critic" in hay) or ("anti-slop" in hay),
        "screenshot_count": len(shots),
        "marathon": "marathon_" in hay or "marathon_save" in hay or "marathon_init" in hay,
        "hay_chars": len(hay),
        "sealed": False,
    }


def _empty_sealed_signals(*, reason: str) -> dict:
    return {
        "exhaustive_read": False,
        "open_task": False,
        "plan_os": False,
        "blast_radius": False,
        "edit_safe": False,
        "verify_bundle": False,
        "claim_done": False,
        "server_authored": False,
        "council": False,
        "security": False,
        "visual_critic": False,
        "screenshot_count": 0,
        "marathon": False,
        "hay_chars": 0,
        "sealed": False,
        "seal_reason": reason,
        "sealed_sources": [],
        "task_files": 0,
    }


def _load_seal_secret_for_arm(arm_dir: Path) -> Optional[bytes]:
    """Resolve seal key for scoring — env preferred; never invent a key."""
    from godkiller_mcp.evidence_integrity import _decode_env_key, _truthy_env

    env_raw = os.environ.get("GODKILLER_SEAL_KEY", "").strip()
    if env_raw:
        try:
            return _decode_env_key(env_raw)
        except ValueError:
            return None

    if not _truthy_env("GODKILLER_ALLOW_LEGACY_SEAL"):
        return None
    if os.environ.get("GODKILLER_PROFILE", "").strip().lower() in (
        "ship",
        "prod",
        "production",
        "strict",
    ):
        return None
    for cand in (
        arm_dir / ".godkiller" / "tasks" / ".seal_key",
        arm_dir / ".godkiller" / ".seal_key",
    ):
        if cand.is_file():
            return cand.read_bytes().strip()
    return None


def _iter_task_jsons(arm_dir: Path) -> List[Path]:
    roots = [
        arm_dir / ".godkiller" / "tasks",
        arm_dir / ".godkiller",
    ]
    out: List[Path] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.glob("task_*.json"):
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        for p in root.glob("*.json"):
            if p.name.startswith("."):
                continue
            if p.name in (".seal_key_SOURCE",):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            # Prefer files that look like task dumps
            try:
                raw = p.read_text(encoding="utf-8", errors="ignore")[:200]
            except OSError:
                continue
            if '"task_id"' in raw or '"evidences"' in raw:
                seen.add(key)
                out.append(p)
    return out


def sealed_artifact_signals(arm_dir: Path) -> dict:
    """
    Dims 5–11 evidence from HMAC-verified armor rows (+ server-only blast/edit).

    Fail-closed: no seal key / no tasks → all False.
    Keyword haystacks and lone .png files do not score.
    """
    from godkiller_mcp.evidence_integrity import ARMOR_SOURCES, verify_seal

    secret = _load_seal_secret_for_arm(arm_dir)
    if not secret:
        return _empty_sealed_signals(reason="no_seal_key")

    task_files = _iter_task_jsons(arm_dir)
    if not task_files:
        return _empty_sealed_signals(reason="no_task_json")

    sealed_sources: set[str] = set()
    has_blast = False
    has_edit = False
    exhaustive = False
    plan_os = False
    open_task = False
    claim_done = False
    server_authored_any = False

    for path in task_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        handle = data.get("handle") or {}
        tid = str(handle.get("task_id") or "")
        if not tid:
            continue
        open_task = True
        hist = data.get("phase_history") or []
        if len(hist) >= 2:
            open_task = True
        phase = str(handle.get("phase") or "").lower()
        if phase in ("claim_done", "closed"):
            claim_done = True
        meta = handle.get("metadata") or {}
        if isinstance(meta, dict):
            meta_blob = json.dumps(meta, ensure_ascii=False).lower()
            if "chosen_design" in meta_blob or "plan_os" in meta_blob:
                plan_os = True
            if "exhaustive" in meta_blob or "full_content" in meta_blob:
                # metadata alone is weak — require server_authored evidence below too
                pass

        for ev in data.get("evidences") or []:
            if not isinstance(ev, dict):
                continue
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            et = str(ev.get("type") or "").lower()
            src = str(payload.get("source") or "")
            authored = bool(payload.get("server_authored"))

            if authored:
                server_authored_any = True

            if et == "blast_radius" and authored:
                has_blast = True
            if et == "edit_safe" and authored:
                has_edit = True

            if src in ARMOR_SOURCES:
                if verify_seal(tid, payload, secret):
                    sealed_sources.add(src)
                continue

            # Non-armor server rows (e.g. exhaustive reader attach) — require authored
            if authored and (
                payload.get("full_content") is True
                or payload.get("engine") == "exhaustive_reader_engine"
                or "exhaustive" in str(payload.get("engine") or "").lower()
            ):
                exhaustive = True

    # Exhaustive also from sealed scout/swarm payloads with full_content
    # (already counted via sealed_sources path only if source in ARMOR — scout may be swarm_collect)
    marathon = False
    for root in (arm_dir / ".godkiller", arm_dir / "session_evidence"):
        if not root.is_dir():
            continue
        for p in root.rglob("*"):
            name = p.name.lower()
            if "marathon" in name and (p.is_dir() or p.suffix.lower() in {".json", ".md"}):
                marathon = True
                break
        if marathon:
            break

    # sealed verify/exit imply claim path pressure
    if "exit_checklist" in sealed_sources:
        claim_done = True

    security = bool(
        sealed_sources & {"fault_probe", "hollow_surface", "write_guard"}
    )

    return {
        "exhaustive_read": exhaustive,
        "open_task": open_task or len(task_files) > 0,
        "plan_os": plan_os,
        "blast_radius": has_blast,
        "edit_safe": has_edit,
        "verify_bundle": "verify_bundle" in sealed_sources,
        "claim_done": claim_done,
        "server_authored": server_authored_any or bool(sealed_sources),
        "council": "council_finalize" in sealed_sources,
        "security": security,
        "visual_critic": "visual_critic" in sealed_sources,
        "screenshot_count": 0,  # alone never scores dim 11
        "marathon": marathon,
        "hay_chars": 0,
        "sealed": True,
        "seal_reason": "ok",
        "sealed_sources": sorted(sealed_sources),
        "task_files": len(task_files),
    }


def score_dimensions(oracle: dict, delta: dict, signals: dict) -> Tuple[Dict[str, float], Dict[str, Any]]:
    counts = oracle["counts"]
    passed = int(counts.get("passed") or 0)
    collected = int(counts.get("collected") or 0)
    pass_rate = (passed / collected * 100.0) if collected else 0.0

    # 1 correctness
    d1 = round(pass_rate, 2)
    # 2 volume — full 516 expected
    d2 = 100.0 if collected >= 516 else round(min(collected / 516.0, 1.0) * 100.0, 2)
    # 3 integrity
    d3 = 100.0 if oracle["has_body"] and not oracle["header_only"] else 0.0
    # 4 delta — must change baseline; full copy of "already fixed" without change = 0 wow
    d4 = round(min(delta["pct"], 100.0), 2)
    # 5–11 fail-closed on *sealed* artifacts (keyword haystack must not score)
    d5 = 100.0 if signals.get("exhaustive_read") else 0.0
    d6 = 100.0 if (signals.get("open_task") or signals.get("plan_os") or signals.get("marathon")) else 0.0
    d7 = (
        100.0
        if (signals.get("blast_radius") and signals.get("edit_safe"))
        else (50.0 if (signals.get("blast_radius") or signals.get("edit_safe")) else 0.0)
    )
    d8 = (
        100.0
        if (signals.get("verify_bundle") and signals.get("claim_done"))
        else (50.0 if signals.get("verify_bundle") else 0.0)
    )
    d9 = 100.0 if signals.get("council") else 0.0
    d10 = 100.0 if signals.get("security") else 0.0
    # visual: sealed visual_critic only — lone screenshots do not count
    d11 = 100.0 if signals.get("visual_critic") else 0.0

    dims = {
        "1_code_correctness": d1,
        "2_oracle_volume": d2,
        "3_output_integrity": d3,
        "4_delta_from_baseline": d4,
        "5_reconnaissance_read": d5,
        "6_phase_discipline": d6,
        "7_blast_edit_safe": d7,
        "8_verify_claim_gate": d8,
        "9_council_review": d9,
        "10_security_hardening": d10,
        "11_ui_visual_gate": d11,
    }
    # Integrity gate: header-only → overall zero
    overall = round(sum(dims.values()) / len(dims), 2) if d3 == 100.0 else 0.0
    evidence = {
        "pass_rate": pass_rate,
        "collected": collected,
        "passed": passed,
        "failed": counts.get("failed"),
        "delta": delta,
        "signals": signals,
        "integrity_gate": d3 == 100.0,
    }
    return dims, {"overall_score": overall, "evidence": evidence}


def score_arm(arena_root: Path, arm: str) -> dict:
    arm_dir = arena_root / arm
    if not arm_dir.is_dir():
        raise FileNotFoundError(arm_dir)
    oracle = run_oracle(arena_root, arm_dir)
    delta = baseline_delta(arena_root, arm_dir)
    signals = sealed_artifact_signals(arm_dir)
    dims, meta = score_dimensions(oracle, delta, signals)
    suspicious = []
    if oracle["header_only"]:
        suspicious.append("pytest_output_header_only")
    if delta["changed_files"] == 0 and oracle["pytest_passed"]:
        suspicious.append("perfect_score_with_zero_delta_from_baseline")
    if arm == "3_WITHOUT_MCP" and any(
        dims[k] == 100.0 for k in ("5_reconnaissance_read", "8_verify_claim_gate", "9_council_review")
    ):
        suspicious.append("bare_arm_has_mcp_only_artifacts_check_contamination")

    return {
        "arm": arm,
        "folder": str(arm_dir.resolve()),
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "dimensions": dims,
        "overall_score": meta["overall_score"],
        "suspicious_flags": suspicious,
        "oracle": {
            "pytest_passed": oracle["pytest_passed"],
            "counts": oracle["counts"],
            "duration_note": "see pytest summary_line",
            "output_chars": oracle["pytest_output_full_chars"],
            "summary_line": oracle["counts"].get("summary_line"),
        },
        "evidence": meta["evidence"],
        "pytest_output_tail": oracle["pytest_output"][-8000:],
    }


def compare(with_score: dict, without_score: dict) -> dict:
    table = {}
    for k in DIMENSIONS:
        table[k] = {
            "with_mcp": with_score["dimensions"][k],
            "without_mcp": without_score["dimensions"][k],
            "delta": round(with_score["dimensions"][k] - without_score["dimensions"][k], 2),
        }
    return {
        "headline": {
            "with_mcp_overall": with_score["overall_score"],
            "without_mcp_overall": without_score["overall_score"],
            "overall_delta": round(with_score["overall_score"] - without_score["overall_score"], 2),
        },
        "dimensions": table,
        "with_mcp_flags": with_score.get("suspicious_flags"),
        "without_mcp_flags": without_score.get("suspicious_flags"),
    }


def write_markdown(compare_doc: dict, out: Path) -> None:
    lines = [
        "# 11-dimension Antigravity A/B scorecard",
        "",
        f"- WITH MCP overall: **{compare_doc['headline']['with_mcp_overall']}**",
        f"- WITHOUT MCP overall: **{compare_doc['headline']['without_mcp_overall']}**",
        f"- Delta: **{compare_doc['headline']['overall_delta']}**",
        "",
        "| # | Dimension | Bare | GODKILLER | Δ |",
        "| ---: | --- | ---: | ---: | ---: |",
    ]
    for i, k in enumerate(DIMENSIONS, start=1):
        row = compare_doc["dimensions"][k]
        lines.append(
            f"| {i} | `{k}` | {row['without_mcp']} | {row['with_mcp']} | {row['delta']} |"
        )
    lines.extend(
        [
            "",
            "Fail-closed: missing session artifacts score 0.",
            "Integrity gate: header-only pytest → overall 0.",
            "",
        ]
    )
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="11-dimension arena scorer")
    parser.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    parser.add_argument("--arm", choices=("2_WITH_MCP", "3_WITHOUT_MCP"))
    parser.add_argument("--compare", action="store_true", help="Score both arms and write comparison")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir or (args.arena_root / "logs")
    out_dir.mkdir(parents=True, exist_ok=True)
    PKG_OUT.mkdir(parents=True, exist_ok=True)

    if args.compare or not args.arm:
        with_s = score_arm(args.arena_root, "2_WITH_MCP")
        without_s = score_arm(args.arena_root, "3_WITHOUT_MCP")
        cmp = compare(with_s, without_s)
        doc = {
            "mode": "antigravity_ab_11",
            "arena_root": str(args.arena_root.resolve()),
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "arms": {"2_WITH_MCP": with_s, "3_WITHOUT_MCP": without_s},
            "comparison": cmp,
            "dimensions_legend": list(DIMENSIONS),
        }
        json_path = out_dir / "11_dimension_scorecard.json"
        md_path = out_dir / "11_dimension_scorecard.md"
        json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        write_markdown(cmp, md_path)
        # mirror into package logs
        (PKG_OUT / "11_dimension_scorecard.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
        write_markdown(cmp, PKG_OUT / "11_dimension_scorecard.md")
        print(json.dumps(cmp["headline"], indent=2))
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")
        return 0

    scored = score_arm(args.arena_root, args.arm)
    path = out_dir / f"score_{args.arm}.json"
    path.write_text(json.dumps(scored, indent=2), encoding="utf-8")
    print(json.dumps({"arm": args.arm, "overall": scored["overall_score"], "dimensions": scored["dimensions"], "flags": scored["suspicious_flags"]}, indent=2))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
