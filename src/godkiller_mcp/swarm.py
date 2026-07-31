"""GODKILLER swarm — real multi-role recon before edits (no mock executed:false).

Modes:
  host  — returns parallel briefs; IDE model fills each role; collect binds evidence
  api   — ThreadPoolExecutor + LLM calls when API key present (real parallel)

Claim gate: swarm_collect must show all roles with non-empty findings;
attacker must record at least one issue or explicit must_fix.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from godkiller_mcp.ship_mode import env_disables, relax_enabled

ROLES = ("scout", "attacker", "planner", "verifier")

ROLE_BRIEFS = {
    "scout": (
        "You are SCOUT. Map the real files/APIs/tests relevant to the goal. "
        "No fluff. Return JSON: "
        '{"findings":["..."],"paths":["..."],"open_questions":["..."],"confidence":0-10}'
    ),
    "attacker": (
        "You are ATTACKER. Try to break the plan/code: security, race, empty states, "
        "placeholders, shallow tests. Be hostile. Return JSON: "
        '{"findings":["..."],"must_fix":["..."],"severity":0-10,"vote":"REJECT"|"CAUTION"|"OK"}'
    ),
    "planner": (
        "You are PLANNER. Produce a minimal ordered edit plan from scout+attacker. "
        "Return JSON: "
        '{"steps":["..."],"paths":["..."],"risks":["..."],"confidence":0-10}'
    ),
    "verifier": (
        "You are VERIFIER. Define how we prove done on disk (commands, probes). "
        "Return JSON: "
        '{"commands":["python -m pytest -q"],"checks":["..."],"fail_closed":true}'
    ),
}

_SESSIONS: Dict[str, "SwarmSession"] = {}


@dataclass
class SwarmSession:
    session_id: str
    goal: str
    workspace: str
    mode: str
    task_id: str = ""
    roles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    briefs: List[Dict[str, Any]] = field(default_factory=list)


def spawn_swarm(
    goal: str,
    *,
    workspace: str = ".",
    mode: str = "host",
    task_id: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    import os

    sid = f"swarm_{uuid.uuid4().hex[:10]}"
    context = context or {}
    context_raw = json.dumps(context, ensure_ascii=False)
    context_chars = len(context_raw)
    keep = 3000
    context_truncated = context_chars > keep
    context_kept = context_raw[:keep]
    if context_truncated:
        context_kept = (
            f"{context_kept}\n…[TRUNCATED total={context_chars} kept={keep}]"
        )
    briefs = []
    for role in ROLES:
        briefs.append(
            {
                "role": role,
                "system": ROLE_BRIEFS[role],
                "user_brief": (
                    f"GOAL:\n{goal[:4000]}\n\n"
                    f"WORKSPACE: {workspace}\n"
                    f"CONTEXT:\n{context_kept}\n\n"
                    f"Play ONLY {role}. Respond with JSON only."
                ),
                "context_truncated": context_truncated,
                "context_chars": context_chars,
            }
        )
    session = SwarmSession(
        session_id=sid,
        goal=goal,
        workspace=workspace,
        mode=mode,
        task_id=task_id,
        briefs=briefs,
    )
    _SESSIONS[sid] = session

    out: Dict[str, Any] = {
        "source": "swarm_spawn",
        "server_authored": True,
        "session_id": sid,
        "mode": mode,
        "roles": list(ROLES),
        "goal": goal,
        "workspace": workspace,
        "task_id": task_id,
        "phase": "awaiting_roles",
        "agent_scripts": briefs,
        "context_truncated": context_truncated,
        "context_chars": context_chars,
        "instructions": (
            "Run the four role briefs (parallel in the IDE if possible). "
            "Then swarm.collect / swarm_submit each role with real JSON findings. "
            "Attacker must not rubber-stamp."
            + (
                " Context was truncated — use godkiller_exhaustive_read / gk_code.read_full "
                "before treating the brief as complete."
                if context_truncated
                else ""
            )
        ),
    }

    # Server-side scout (and optional full auto roles) — do not trust Antigravity to explore
    auto_env = os.environ.get("GODKILLER_SWARM_AUTO", "1").strip().lower()
    want_auto = mode in ("auto", "server") or (
        mode == "host" and auto_env not in ("0", "false", "off", "no")
    )
    if want_auto and not relax_enabled():
        auto_roles = _server_auto_roles(goal, workspace)
        session.roles.update(auto_roles)
        out["server_auto_roles"] = list(auto_roles.keys())
        out["scout_auto"] = auto_roles.get("scout")
        missing = [r for r in ROLES if r not in session.roles]
        if not missing:
            out["phase"] = "ready_to_collect"
            out["instructions"] = (
                "Server filled roles from disk recon. Call swarm_collect "
                "(or swarm_submit to override)."
            )
        else:
            out["phase"] = "awaiting_roles"
            out["missing_roles"] = missing
            out["instructions"] = (
                f"Server auto-filled {list(auto_roles.keys())}. "
                f"Still need host/API submit for: {missing} "
                "(attacker must be real pressure — no canned Server attacker)."
            )

    if mode == "api":
        api_result = _run_api_swarm(session, context)
        out.update(api_result)
    return out


def require_swarm_before_edit(state) -> Tuple[bool, str]:
    """Block check_edit_safe when swarm is required and collect not passed."""
    return claim_swarm_gate(state)


def _server_auto_roles(goal: str, workspace: str) -> Dict[str, Dict[str, Any]]:
    """Disk recon for scout (+ light planner/verifier). Never invent attacker pressure."""
    from pathlib import Path

    from godkiller_mcp.code_intel import HyperSearchEngine, RepoMapGenerator
    from godkiller_mcp.evidence_quality import is_hollow_text

    root = Path(workspace).resolve() if workspace else Path(".").resolve()
    findings: List[str] = []
    paths: List[str] = []
    try:
        gen = RepoMapGenerator(str(root))
        map_text = gen.get_repo_map(max_tokens=800)
        if map_text and len(map_text.strip()) > 40:
            findings.append(f"repo_map:{map_text[:500].replace(chr(10), ' | ')}")
            for line in map_text.splitlines():
                line = line.strip().strip("-*`). ")
                if line.endswith((".py", ".ts", ".tsx", ".js", ".go", ".rs")) and len(line) < 200:
                    paths.append(line.split()[0] if line.split() else line)
    except Exception as exc:
        findings.append(f"repo_map_error:{exc}"[:200])

    tokens = [
        t
        for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", goal or "")
        if t.lower() not in ("that", "this", "with", "from")
    ]
    searcher = HyperSearchEngine()
    for tok in tokens[:5]:
        try:
            res = searcher.search(tok, search_path=str(root), max_results=8)
            hits = res.get("matches") or res.get("results") or res.get("files") or []
            if isinstance(hits, list) and hits:
                findings.append(f"search:{tok} hits={len(hits)}")
                for h in hits[:5]:
                    if isinstance(h, dict):
                        p = h.get("path") or h.get("file") or ""
                    else:
                        p = str(h)
                    if p:
                        paths.append(str(p).replace("\\", "/")[:200])
        except Exception:
            continue

    paths = list(dict.fromkeys([p for p in paths if p]))[:30]
    clean_findings = []
    for f in findings:
        hollow, _ = is_hollow_text(f, min_chars=8, min_unique_words=2)
        if not hollow:
            clean_findings.append(f[:400])
    if not clean_findings:
        clean_findings = [f"scout: workspace={root.name} paths_seen={len(paths)}"]

    scout = _normalize_role(
        "scout",
        {
            "findings": clean_findings[:20],
            "paths": paths,
            "confidence": 7,
            "paging_hint": "Brief truncated — use godkiller_exhaustive_read / gk_code.read_full on paths before edit",
        },
    )
    planner = _normalize_role(
        "planner",
        {
            "findings": [f"Plan from goal: {(goal or '')[:200]}"],
            "steps": [
                "Read scout paths (full file via read_full if brief truncated)",
                "blast_radius + check_edit_safe one file",
                "verify_bundle pytest",
            ],
            "paths": paths[:10],
            "confidence": 6,
        },
    )
    verifier = _normalize_role(
        "verifier",
        {
            "findings": ["Prove with pytest on disk"],
            "commands": ["python -m pytest -q"],
            "checks": ["verify_bundle passed", "swarm_collect sealed"],
            "fail_closed": True,
        },
    )
    # Attacker intentionally omitted — host/API must submit real pressure
    return {
        "scout": scout,
        "planner": planner,
        "verifier": verifier,
    }


def submit_role(
    session_id: str,
    role: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    session = _SESSIONS.get(session_id)
    if not session:
        return {"ok": False, "error": f"Unknown swarm session {session_id}"}
    role = role.lower().strip()
    if role not in ROLES:
        return {"ok": False, "error": f"Invalid role {role}; need one of {ROLES}"}
    cleaned = _normalize_role(role, payload)
    session.roles[role] = cleaned
    missing = [r for r in ROLES if r not in session.roles]
    return {
        "ok": True,
        "source": "swarm_submit",
        "session_id": session_id,
        "role": role,
        "recorded": cleaned,
        "missing_roles": missing,
        "phase": "ready_to_collect" if not missing else "awaiting_roles",
    }


def collect_swarm(session_id: str) -> Dict[str, Any]:
    session = _SESSIONS.get(session_id)
    if not session:
        return {
            "ok": False,
            "source": "swarm_collect",
            "server_authored": True,
            "error": f"Unknown swarm session {session_id}",
            "passed": False,
        }
    missing = [r for r in ROLES if r not in session.roles]
    if missing:
        return {
            "ok": False,
            "source": "swarm_collect",
            "server_authored": True,
            "session_id": session_id,
            "passed": False,
            "missing_roles": missing,
            "reason": f"swarm incomplete — missing {missing}",
        }
    ok, reason = _swarm_quality(session.roles)
    return {
        "ok": ok,
        "source": "swarm_collect",
        "server_authored": True,
        "session_id": session_id,
        "passed": ok,
        "reason": reason,
        "roles": session.roles,
        "goal": session.goal,
        "workspace": session.workspace,
        "task_id": session.task_id,
        "write_allow_paths": _paths_from_roles(session.roles),
    }


def claim_swarm_gate(state) -> Tuple[bool, str]:
    if relax_enabled():
        return True, "swarm skipped (DEV_RELAX)"
    if env_disables("GODKILLER_SWARM"):
        return True, "swarm disabled (relax only)"
    # Opt-in strict: require swarm when metadata asks or GODKILLER_SWARM_REQUIRED=1
    meta = state.handle.metadata or {}
    required = meta.get("require_swarm") is True or os.environ.get(
        "GODKILLER_SWARM_REQUIRED", ""
    ).strip() in ("1", "true", "yes", "on")
    if not required:
        return True, "swarm not required for this task"

    for ev in reversed(list(getattr(state, "evidences", []) or [])):
        payload = ev.payload or {}
        if payload.get("source") != "swarm_collect":
            continue
        if payload.get("server_authored") is not True:
            continue
        if payload.get("passed") is True:
            return True, "swarm_collect passed"
        return False, f"swarm_collect not passed: {payload.get('reason')}"
    return (
        False,
        "Forced gate: swarm required — spawn → submit all roles → collect (passed) "
        "before claim_done",
    )


def _normalize_role(role: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    findings = data.get("findings") or data.get("checks") or data.get("steps") or []
    if isinstance(findings, str):
        findings = [findings]
    findings = [str(x).strip() for x in findings if str(x).strip()]
    must_fix = data.get("must_fix") or []
    if isinstance(must_fix, str):
        must_fix = [must_fix]
    must_fix = [str(x).strip() for x in must_fix if str(x).strip()]
    paths = data.get("paths") or []
    if isinstance(paths, str):
        paths = [paths]
    return {
        "role": role,
        "findings": findings[:40],
        "must_fix": must_fix[:20],
        "paths": [str(p) for p in paths[:40] if p],
        "vote": str(data.get("vote") or "").upper(),
        "severity": int(data.get("severity") or data.get("confidence") or 0),
        "commands": list(data.get("commands") or [])[:20],
        "raw": data,
    }


def _swarm_quality(roles: Dict[str, Dict[str, Any]]) -> Tuple[bool, str]:
    from godkiller_mcp.evidence_quality import is_hollow_text

    _CANNED = (
        "server attacker:",
        "remove stub copy and untested branches",
        "server-stub",
    )
    for role in ROLES:
        r = roles.get(role) or {}
        if (r.get("raw") or {}).get("server_stub") is True:
            return False, f"swarm role {role} marked server_stub — not claim-grade"
        body = r.get("findings") or r.get("commands") or []
        if not body and not r.get("must_fix"):
            return False, f"swarm role {role} empty — no mock/empty collects"
    attacker = roles.get("attacker") or {}
    findings = [str(x) for x in (attacker.get("findings") or [])]
    if not findings and not attacker.get("must_fix"):
        return False, "attacker produced no findings/must_fix — refute-first failed"
    for f in findings:
        low = f.lower()
        for bad in _CANNED:
            if bad in low:
                return False, "attacker findings look like canned server stub — submit real pressure"
        hollow, why = is_hollow_text(f, min_chars=16, min_unique_words=4)
        if hollow:
            return False, f"attacker finding hollow: {why}"
    scout_paths = set((roles.get("scout") or {}).get("paths") or [])
    if scout_paths:
        atk_paths = set(attacker.get("paths") or [])
        # Also accept path mention inside findings text
        blob = " ".join(findings).replace("\\", "/")
        grounded = bool(atk_paths & scout_paths) or any(
            str(p) in blob for p in list(scout_paths)[:12]
        )
        if not grounded:
            return (
                False,
                "attacker must cite ≥1 scout path (paths[] or in findings) when scout has paths",
            )
    blob = " ".join(" ".join(r.get("findings") or []) for r in roles.values()).lower()
    for bad in ("coming soon", "lorem ipsum", "placeholder", "todo later", "mockup"):
        if bad in blob:
            return False, f"swarm findings contain hollow signal: {bad}"
    return True, "swarm roles complete with attacker pressure"


def _paths_from_roles(roles: Dict[str, Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for r in roles.values():
        out.extend(r.get("paths") or [])
    return list(dict.fromkeys(out))


def _run_api_swarm(session: SwarmSession, context: Dict[str, Any]) -> Dict[str, Any]:
    from godkiller_mcp.llm_client import load_llm_config, make_chat_fn, parse_agent_json

    cfg = load_llm_config()
    if cfg is None:
        return {
            "api_ran": False,
            "error": "API swarm needs GODKILLER_LLM_API_KEY or OPENAI_API_KEY — use mode=host",
            "fallback": "host",
            "passed": False,
        }
    chat = make_chat_fn(cfg)

    def _one(brief: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        role = brief["role"]
        text = chat(brief["system"], brief["user_brief"])
        parsed = parse_agent_json(text)
        if not isinstance(parsed, dict):
            parsed = {"findings": [str(text)[:500]]}
        return role, _normalize_role(role, parsed)

    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(_one, b) for b in session.briefs]
        for fut in as_completed(futs):
            try:
                role, cleaned = fut.result()
                session.roles[role] = cleaned
            except Exception as exc:
                errors.append(str(exc))

    if errors and len(session.roles) < len(ROLES):
        return {
            "api_ran": True,
            "passed": False,
            "error": "; ".join(errors[:3]),
            "roles_partial": session.roles,
        }
    ok, reason = _swarm_quality(session.roles)
    return {
        "api_ran": True,
        "passed": ok,
        "reason": reason,
        "roles": session.roles,
        "phase": "collected" if ok else "failed",
        "write_allow_paths": _paths_from_roles(session.roles),
    }
