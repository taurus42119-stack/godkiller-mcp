"""Per-file Think → Plan → Edit → Verify gate for /ultradeep (additive).

Does not replace marathon one-phase-per-turn pacing. It stacks on top:
within the CURRENT plan Phase, edits must go file-by-file with recorded
think + plan evidence before touching code.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

FILE_STAGES = ("think", "plan", "edit", "verify", "done")
MIN_THINK_CHARS = 120
MIN_PLAN_CHARS = 80
MIN_PLAN_REFUTE_FINDINGS = 8
MIN_PLAN_REFUTE_SEARCHES = 5


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(path: str) -> str:
    return path.replace("\\", "/").strip()


def plan_refute_status(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = metadata or {}
    pr = meta.get("ultradeep_plan_refute")
    if not isinstance(pr, dict):
        return {"status": "missing", "ok": False}
    return pr


def require_plan_refute_hold(metadata: Optional[Dict[str, Any]]) -> tuple[bool, str]:
    """Block edits until plan_refute status is HOLD (after valid 9-step plan)."""
    from godkiller_mcp.ship_mode import env_disables, relax_enabled

    if relax_enabled():
        return True, "plan_refute skipped (DEV_RELAX)"
    if env_disables("GODKILLER_PLAN_REFUTE"):
        return True, "plan_refute disabled (relax only)"
    meta = metadata or {}
    # Only enforce when a validated plan exists (or plan_dict present)
    plan_meta = meta.get("plan_validation") or {}
    if not plan_meta.get("valid") and not meta.get("plan_dict"):
        return True, "plan_refute not required yet (no validated plan)"
    pr = plan_refute_status(meta)
    if pr.get("status") == "HOLD" and pr.get("ok") is True:
        return True, "plan_refute HOLD"
    if pr.get("status") == "REOPEN":
        return (
            False,
            f"ultradeep plan_refute REOPEN — fix steps {pr.get('broken_steps') or []} "
            "then ultradeep_plan_refute again",
        )
    return (
        False,
        "Forced wake: call ultradeep_plan_refute (≥8 attacks on 9-step plan + ≥5 searches) "
        "and get HOLD before edit_safe",
    )


def record_plan_refute(
    *,
    findings: Sequence[Any],
    search_queries: Sequence[str],
    broken_steps: Optional[Sequence[str]] = None,
    decision: str = "HOLD",
) -> Dict[str, Any]:
    """Validate refute payload; return metadata blob for ultradeep_plan_refute."""
    from godkiller_mcp.evidence_quality import dedupe_findings, is_hollow_text

    cleaned: List[str] = []
    hollow_rejects = 0
    for f in findings or []:
        if isinstance(f, dict):
            text = str(f.get("text") or f.get("finding") or f.get("attack") or "").strip()
            step = str(f.get("step") or f.get("plan_step") or "").strip()
            line = f"{step}: {text}".strip(": ").strip() if step else text
        else:
            line = str(f).strip()
        hollow, _why = is_hollow_text(line, min_chars=16, min_unique_words=4)
        if hollow:
            hollow_rejects += 1
            continue
        cleaned.append(line[:500])
    cleaned, dupes = dedupe_findings(cleaned)
    queries_raw = [str(q).strip() for q in (search_queries or []) if str(q).strip()]
    queries = []
    for q in queries_raw:
        hollow, _ = is_hollow_text(q, min_chars=8, min_unique_words=2)
        if not hollow:
            queries.append(q)
    queries, _ = dedupe_findings(queries)
    decision_u = str(decision or "HOLD").upper().strip()
    if decision_u not in ("HOLD", "REOPEN"):
        decision_u = "REOPEN" if broken_steps else "HOLD"

    if len(cleaned) < MIN_PLAN_REFUTE_FINDINGS:
        return {
            "ok": False,
            "status": "blocked",
            "reason": (
                f"plan_refute needs ≥{MIN_PLAN_REFUTE_FINDINGS} unique substantial findings "
                f"(got {len(cleaned)}; hollow_rejected={hollow_rejects}, dupes={dupes}) "
                "— asdf/nits spam does not wake the brain"
            ),
            "findings": cleaned,
            "search_queries": queries,
        }
    if len(queries) < MIN_PLAN_REFUTE_SEARCHES:
        return {
            "ok": False,
            "status": "blocked",
            "reason": (
                f"plan_refute needs ≥{MIN_PLAN_REFUTE_SEARCHES} distinct non-hollow search queries "
                f"(got {len(queries)})"
            ),
            "findings": cleaned,
            "search_queries": queries,
        }
    broken = [str(s) for s in (broken_steps or []) if s]
    if decision_u == "REOPEN" or broken:
        return {
            "ok": False,
            "status": "REOPEN",
            "reason": "plan_refute REOPEN — patch broken plan steps then re-refute",
            "broken_steps": broken or ["unspecified"],
            "findings": cleaned[:40],
            "search_queries": queries[:20],
            "updated_at": _utcnow(),
            "source": "ultradeep_plan_refute",
            "server_authored": True,
        }
    return {
        "ok": True,
        "status": "HOLD",
        "reason": "plan_refute HOLD — may proceed to per-file think→plan→edit",
        "findings": cleaned[:40],
        "search_queries": queries[:20],
        "broken_steps": [],
        "updated_at": _utcnow(),
        "source": "ultradeep_plan_refute",
        "server_authored": True,
        "quality": {"hollow_rejected": hollow_rejects, "dupes_dropped": dupes},
    }


def empty_file_gate(enabled: bool = True) -> Dict[str, Any]:
    return {
        "enabled": enabled,
        "queue": [],  # ordered paths
        "files": {},  # path -> {stage, think, plan, hypotheses, tools_used, updated_at}
        "current": None,
        "max_files_per_edit_call": 1,
        "require_hypotheses": 3,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }


def get_gate(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = metadata or {}
    gate = meta.get("ultradeep_file_gate")
    if not isinstance(gate, dict):
        return empty_file_gate(enabled=False)
    # ensure shape
    gate.setdefault("enabled", True)
    gate.setdefault("queue", [])
    gate.setdefault("files", {})
    gate.setdefault("current", None)
    gate.setdefault("max_files_per_edit_call", 1)
    gate.setdefault("require_hypotheses", 3)
    return gate


def queue_files(
    gate: Dict[str, Any],
    paths: Sequence[str],
    *,
    replace: bool = False,
) -> Dict[str, Any]:
    paths_n = [_norm(p) for p in paths if p and str(p).strip()]
    if replace:
        gate["queue"] = list(dict.fromkeys(paths_n))
        gate["files"] = {
            p: gate.get("files", {}).get(p)
            or {
                "stage": "think",
                "think": "",
                "plan": "",
                "hypotheses": [],
                "tools_used": [],
                "updated_at": _utcnow(),
            }
            for p in gate["queue"]
        }
    else:
        for p in paths_n:
            if p not in gate["queue"]:
                gate["queue"].append(p)
            gate.setdefault("files", {})
            if p not in gate["files"]:
                gate["files"][p] = {
                    "stage": "think",
                    "think": "",
                    "plan": "",
                    "hypotheses": [],
                    "tools_used": [],
                    "updated_at": _utcnow(),
                }
    if not gate.get("current") and gate["queue"]:
        gate["current"] = gate["queue"][0]
    gate["updated_at"] = _utcnow()
    return gate


def _ensure_file(gate: Dict[str, Any], path: str) -> Dict[str, Any]:
    path = _norm(path)
    gate.setdefault("files", {})
    if path not in gate["files"]:
        gate["files"][path] = {
            "stage": "think",
            "think": "",
            "plan": "",
            "hypotheses": [],
            "tools_used": [],
            "updated_at": _utcnow(),
        }
    if path not in gate.get("queue", []):
        gate.setdefault("queue", []).append(path)
    if not gate.get("current"):
        gate["current"] = path
    return gate["files"][path]


def record_think(
    gate: Dict[str, Any],
    path: str,
    think: str,
    *,
    hypotheses: Optional[Sequence[str]] = None,
    tools_used: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    path = _norm(path)
    entry = _ensure_file(gate, path)
    think = (think or "").strip()
    hyps = [h.strip() for h in (hypotheses or []) if h and str(h).strip()]
    need = int(gate.get("require_hypotheses") or 3)
    if len(think) < MIN_THINK_CHARS:
        return {
            "ok": False,
            "reason": f"Think notes too short (need ≥{MIN_THINK_CHARS} chars). Deep think required.",
            "gate": gate,
        }
    if len(hyps) < need:
        return {
            "ok": False,
            "reason": f"Need ≥{need} competing hypotheses for this file before plan/edit.",
            "gate": gate,
        }
    entry["think"] = think
    entry["hypotheses"] = hyps
    if tools_used:
        entry["tools_used"] = list(
            dict.fromkeys([*(entry.get("tools_used") or []), *[str(t) for t in tools_used]])
        )
    entry["stage"] = "plan"
    entry["updated_at"] = _utcnow()
    gate["current"] = path
    gate["updated_at"] = _utcnow()
    return {"ok": True, "reason": "Think recorded — next: ultradeep_plan_file for this path.", "gate": gate, "file": entry}


def record_plan(
    gate: Dict[str, Any],
    path: str,
    plan: str,
    *,
    tools_used: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    path = _norm(path)
    entry = _ensure_file(gate, path)
    if entry.get("stage") not in ("plan", "edit", "verify", "done") and not entry.get("think"):
        return {
            "ok": False,
            "reason": "Call ultradeep_think_file first (think → plan → edit).",
            "gate": gate,
        }
    if not entry.get("think") or len(entry.get("hypotheses") or []) < int(gate.get("require_hypotheses") or 3):
        return {
            "ok": False,
            "reason": "Think + ≥3 hypotheses required before plan.",
            "gate": gate,
        }
    plan = (plan or "").strip()
    if len(plan) < MIN_PLAN_CHARS:
        return {
            "ok": False,
            "reason": f"Per-file plan too short (need ≥{MIN_PLAN_CHARS} chars).",
            "gate": gate,
        }
    entry["plan"] = plan
    if tools_used:
        entry["tools_used"] = list(
            dict.fromkeys([*(entry.get("tools_used") or []), *[str(t) for t in tools_used]])
        )
    entry["stage"] = "edit"
    entry["updated_at"] = _utcnow()
    gate["current"] = path
    gate["updated_at"] = _utcnow()
    return {"ok": True, "reason": "Plan recorded — may edit THIS file only via check_edit_safe.", "gate": gate, "file": entry}


def mark_verify(gate: Dict[str, Any], path: str) -> Dict[str, Any]:
    path = _norm(path)
    entry = _ensure_file(gate, path)
    if entry.get("stage") not in ("edit", "verify", "done"):
        return {"ok": False, "reason": "File not in edit stage yet.", "gate": gate}
    entry["stage"] = "verify"
    entry["updated_at"] = _utcnow()
    gate["updated_at"] = _utcnow()
    return {"ok": True, "reason": "Marked verify — run tests/scan then ultradeep_advance_file.", "gate": gate, "file": entry}


def advance_file(gate: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
    path = _norm(path or gate.get("current") or "")
    if not path:
        return {"ok": False, "reason": "No current file.", "gate": gate}
    entry = _ensure_file(gate, path)
    if entry.get("stage") not in ("edit", "verify"):
        return {
            "ok": False,
            "reason": f"Cannot advance from stage={entry.get('stage')}; need edit/verify first.",
            "gate": gate,
        }
    if not entry.get("plan"):
        return {"ok": False, "reason": "Plan missing.", "gate": gate}
    entry["stage"] = "done"
    entry["updated_at"] = _utcnow()
    # move current to next incomplete
    nxt = None
    for p in gate.get("queue") or []:
        st = (gate.get("files") or {}).get(p, {}).get("stage")
        if st != "done":
            nxt = p
            break
    gate["current"] = nxt
    gate["updated_at"] = _utcnow()
    return {
        "ok": True,
        "reason": f"File done: {path}. Next current={nxt or '(queue empty)'}.",
        "gate": gate,
        "next": nxt,
    }


def check_edit_paths(gate: Dict[str, Any], paths: Sequence[str]) -> tuple[bool, str]:
    """Hard gate: at most one file, must be current, must be in edit stage after think+plan."""
    if not gate.get("enabled"):
        return True, "per-file gate disabled"
    paths_n = [_norm(p) for p in paths if p]
    if not paths_n:
        return False, "No paths provided to edit_safe."
    max_n = int(gate.get("max_files_per_edit_call") or 1)
    if len(paths_n) > max_n:
        return (
            False,
            f"ULTRADEEP per-file gate: edit at most {max_n} file(s) per call "
            f"(got {len(paths_n)}). Think→Plan→Edit one file at a time — no batch rush.",
        )
    if not gate.get("queue"):
        return (
            False,
            "ULTRADEEP per-file gate: call ultradeep_queue_files with target paths first.",
        )
    current = gate.get("current")
    target = paths_n[0]
    if current and target != _norm(current):
        return (
            False,
            f"ULTRADEEP per-file gate: current file is `{current}`; "
            f"finish think→plan→edit→advance before touching `{target}`.",
        )
    entry = (gate.get("files") or {}).get(target) or {}
    if not entry.get("think"):
        return False, f"Missing deep think for `{target}` — call ultradeep_think_file."
    if not entry.get("plan") or entry.get("stage") not in ("edit", "verify"):
        return False, f"Missing per-file plan for `{target}` — call ultradeep_plan_file after think."
    return True, f"Per-file gate OK for `{target}` (stage={entry.get('stage')})."


def status_payload(gate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": bool(gate.get("enabled")),
        "current": gate.get("current"),
        "queue": list(gate.get("queue") or []),
        "files": gate.get("files") or {},
        "updated_at": gate.get("updated_at"),
        "loop": "think → plan → edit(one file) → verify → advance → next file",
        "cursor_agent_power": (
            "Use maximal tool swarm: gk_code/search/map/read_full, gk_scan, gk_browser, "
            "gk_evidence, peer MCP jcodemunch + codebase-memory + chrome-devtools, "
            "parallel subagent reconnaissance BEFORE any write."
        ),
    }
