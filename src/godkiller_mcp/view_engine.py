""" /view — adversarial research planning (weaknesses-only + plan refute wake).

Gravity G1–G4 = work scale (not a calendar). One heavy refute wake after draft plan.
Does not edit application code — seals a 9-step Plan OS shaped plan only.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from godkiller_mcp.plan_os import NINE_STEPS

GRAVITY = {
    "G1": {"min_searches": 12, "min_attacks": 8, "min_refute": 20},
    "G2": {"min_searches": 20, "min_attacks": 12, "min_refute": 24},
    "G3": {"min_searches": 28, "min_attacks": 16, "min_refute": 28},
    "G4": {"min_searches": 30, "min_attacks": 20, "min_refute": 30},
}

TAXONOMY = (
    "method",
    "data",
    "claim",
    "stats",
    "ux",
    "security",
    "scale",
    "reproducibility",
    "external_validity",
    "citation",
)

_PRAISE = re.compile(
    r"\b(overall good|looks great|well done|excellent work|balanced review|"
    r"by and large|impressive|solid work|kudos)\b",
    re.I,
)
# Deny-assist only: praise regex never unlocks finalize; weakness tokens still required.


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_view_state(
    *,
    goal: str = "",
    gravity: str = "G2",
    task_id: str = "",
) -> Dict[str, Any]:
    g = gravity.upper().strip()
    if g not in GRAVITY:
        g = "G2"
    return {
        "mode": "view",
        "goal": goal,
        "gravity": g,
        "task_id": task_id,
        "phase": "frame",
        "searches": [],
        "attacks": [],
        "plan_steps": {k: "" for k in NINE_STEPS},
        "refute": [],
        "refute_status": "pending",
        "sealed": False,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "source": "view_engine",
        "server_authored": True,
    }


def get_view(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    meta = metadata or {}
    v = meta.get("view_campaign")
    if not isinstance(v, dict):
        return empty_view_state()
    v.setdefault("searches", [])
    v.setdefault("attacks", [])
    v.setdefault("plan_steps", {k: "" for k in NINE_STEPS})
    v.setdefault("refute", [])
    v.setdefault("refute_status", "pending")
    v.setdefault("sealed", False)
    return v


def thresholds(gravity: str) -> Dict[str, int]:
    return dict(GRAVITY.get(gravity.upper(), GRAVITY["G2"]))


def start_view(goal: str, *, gravity: str = "G2", task_id: str = "") -> Dict[str, Any]:
    state = empty_view_state(goal=goal, gravity=gravity, task_id=task_id)
    state["phase"] = "hunt"
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "view": state,
        "thresholds": thresholds(state["gravity"]),
        "next": "view_record_search — record ≥N searches with real URLs",
        "agent_role": {"may_decide_done": False},
    }


def record_search(
    state: Dict[str, Any],
    *,
    query: str,
    url: str,
    backend: str = "host_web_search",
    note: str = "",
) -> Dict[str, Any]:
    from godkiller_mcp.doi_resolve import cite_with_doi_policy
    from godkiller_mcp.evidence_quality import cite_source_ok, is_hollow_text, unique_hosts
    from godkiller_mcp.ssrf import assert_public_url

    q = (query or "").strip()
    u = (url or "").strip()
    hollow, why = is_hollow_text(q, min_chars=8, min_unique_words=2)
    if hollow:
        return {"ok": False, "reason": f"hollow search query: {why}", "view": state}
    src_ok, src_why = cite_source_ok(u if not u.startswith("doi:") else u)
    if not src_ok:
        return {"ok": False, "reason": src_why, "view": state}
    doi_ok, doi_why, _meta = cite_with_doi_policy(u)
    if not doi_ok:
        return {"ok": False, "reason": doi_why, "view": state}
    if u.startswith("http://") or u.startswith("https://"):
        if "doi.org/" not in u.lower():
            ok_s, reason_s = assert_public_url(u, resolve=True)
            if not ok_s:
                return {"ok": False, "reason": reason_s, "view": state}
    state.setdefault("searches", []).append(
        {
            "query": q[:500],
            "url": u[:1000],
            "backend": (backend or "host")[:80],
            "note": (note or "")[:300],
            "at": _utcnow(),
        }
    )
    thr = thresholds(state.get("gravity") or "G2")
    n = len(state["searches"])
    hosts = unique_hosts(s["url"] for s in state["searches"] if not str(s["url"]).startswith("10."))
    min_hosts = max(3, thr["min_searches"] // 4)
    if n >= thr["min_searches"] and hosts < min_hosts:
        # keep hunting until host diversity OK
        state["phase"] = "hunt"
        state["updated_at"] = _utcnow()
        return {
            "ok": True,
            "view": state,
            "search_count": n,
            "need": thr["min_searches"],
            "unique_hosts": hosts,
            "need_hosts": min_hosts,
            "phase": "hunt",
            "next": f"Need ≥{min_hosts} distinct hosts (have {hosts}) — no single-domain flood",
        }
    if n >= thr["min_searches"] and state.get("phase") == "hunt":
        state["phase"] = "attack"
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "view": state,
        "search_count": n,
        "need": thr["min_searches"],
        "unique_hosts": hosts,
        "phase": state["phase"],
        "next": (
            "view_record_attack"
            if state["phase"] == "attack"
            else f"Keep hunting — {n}/{thr['min_searches']} searches"
        ),
    }


def _valid_cite(attack: Dict[str, Any]) -> Tuple[bool, str]:
    from godkiller_mcp.doi_resolve import cite_with_doi_policy
    from godkiller_mcp.evidence_quality import cite_source_ok, is_hollow_text

    quote = str(attack.get("quote") or "").strip()
    src = str(attack.get("doi_or_url") or attack.get("url") or "").strip()
    locator = str(attack.get("locator") or "").strip()
    stance = str(attack.get("stance") or "").strip().lower()
    tax = str(attack.get("taxonomy") or attack.get("kind") or "").strip().lower()
    hollow, why = is_hollow_text(quote, min_chars=20, min_unique_words=4)
    if hollow:
        return False, f"quote hollow: {why}"
    ok_s, why_s = cite_source_ok(src)
    if not ok_s:
        return False, why_s
    doi_ok, doi_why, doi_meta = cite_with_doi_policy(src)
    if not doi_ok:
        return False, doi_why
    from godkiller_mcp.doi_resolve import quote_bound_to_record

    bind_ok, bind_why = quote_bound_to_record(
        quote,
        doi_meta,
        page_excerpt=str(attack.get("page_excerpt") or attack.get("excerpt") or ""),
    )
    if not bind_ok:
        return False, bind_why
    if src.startswith("http://") or src.startswith("https://"):
        # doi.org URLs already handled above; other http still SSRF
        if "doi.org/" not in src.lower():
            from godkiller_mcp.ssrf import assert_public_url

            ok_u, why_u = assert_public_url(src, resolve=True)
            if not ok_u:
                return False, why_u
    if len(locator) < 2:
        return False, "locator required (page/section/para)"
    if stance not in ("contradicts", "undermines", "supports", "mentions"):
        return False, "stance must be contradicts|undermines|supports|mentions"
    if tax and tax not in TAXONOMY:
        return False, f"taxonomy must be one of {TAXONOMY}"
    # stash for caller
    attack["_doi_resolve"] = doi_meta
    attack["_quote_bind"] = bind_why
    return True, "ok"


def record_attack(state: Dict[str, Any], attack: Dict[str, Any]) -> Dict[str, Any]:
    from godkiller_mcp.evidence_quality import is_hollow_text

    thr = thresholds(state.get("gravity") or "G2")
    if len(state.get("searches") or []) < thr["min_searches"]:
        return {
            "ok": False,
            "reason": f"Hunt incomplete — need ≥{thr['min_searches']} searches first",
            "view": state,
        }
    ok, reason = _valid_cite(attack)
    if not ok:
        return {"ok": False, "reason": reason, "view": state}
    try:
        sev = int(attack.get("severity") or 5)
    except Exception:
        sev = 5
    text_body = str(attack.get("text") or attack.get("weakness") or attack.get("finding") or "")
    hollow_t, why_t = is_hollow_text(text_body, min_chars=12, min_unique_words=3)
    if hollow_t:
        return {"ok": False, "reason": f"attack text hollow: {why_t}", "view": state}
    entry = {
        "text": text_body.strip()[:800],
        "quote": str(attack["quote"]).strip()[:400],
        "doi_or_url": str(attack.get("doi_or_url") or attack.get("url")).strip()[:1000],
        "locator": str(attack.get("locator")).strip()[:120],
        "stance": str(attack.get("stance")).strip().lower(),
        "taxonomy": str(attack.get("taxonomy") or attack.get("kind") or "claim").strip().lower(),
        "severity": max(1, min(10, sev)),
        "outcompete": str(attack.get("outcompete") or "")[:500],
        "doi_resolve": attack.get("_doi_resolve") or {},
        "quote_bind": attack.get("_quote_bind") or "",
        "at": _utcnow(),
    }
    if len(entry["text"]) < 12:
        return {"ok": False, "reason": "attack text/weakness too short", "view": state}
    state.setdefault("attacks", []).append(entry)
    n = len(state["attacks"])
    if n >= thr["min_attacks"] and state.get("phase") in ("hunt", "attack"):
        state["phase"] = "draft"
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "view": state,
        "attack_count": n,
        "need": thr["min_attacks"],
        "phase": state["phase"],
        "next": (
            "view_draft_plan (9-step adversarial)"
            if state["phase"] == "draft"
            else f"More attacks — {n}/{thr['min_attacks']}"
        ),
    }


def draft_plan(state: Dict[str, Any], steps: Dict[str, str]) -> Dict[str, Any]:
    thr = thresholds(state.get("gravity") or "G2")
    if len(state.get("attacks") or []) < thr["min_attacks"]:
        return {
            "ok": False,
            "reason": f"Need ≥{thr['min_attacks']} cited attacks before draft plan",
            "view": state,
        }
    filled = {}
    missing = []
    for key in NINE_STEPS:
        val = str((steps or {}).get(key) or "").strip()
        if len(val) < 40:
            missing.append(key)
        else:
            if _PRAISE.search(val):
                return {
                    "ok": False,
                    "reason": f"plan step {key} contains praise — weaknesses/outcompete only",
                    "view": state,
                }
            filled[key] = val[:4000]
    if missing:
        return {
            "ok": False,
            "reason": f"adversarial 9-step plan incomplete: {missing}",
            "view": state,
        }
    state["plan_steps"] = filled
    state["phase"] = "alarm"
    state["refute_status"] = "pending"
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "view": state,
        "phase": "alarm",
        "next": (
            f"Forced wake: view_refute_plan — ≥{thr['min_refute']} attacks ON THE PLAN "
            "(not the topic). Then view_finalize if HOLD."
        ),
        "plan_os_keys": list(NINE_STEPS),
    }


def refute_plan(
    state: Dict[str, Any],
    *,
    findings: Sequence[Any],
    decision: str = "HOLD",
) -> Dict[str, Any]:
    from godkiller_mcp.evidence_quality import dedupe_findings, is_hollow_text

    if state.get("phase") not in ("alarm", "draft", "seal"):
        if not state.get("plan_steps") or not all(
            str(state["plan_steps"].get(k) or "").strip() for k in NINE_STEPS
        ):
            return {"ok": False, "reason": "draft 9-step plan first", "view": state}
    thr = thresholds(state.get("gravity") or "G2")
    raw_items: List[Dict[str, Any]] = []
    hollow_n = 0
    for f in findings or []:
        if isinstance(f, dict):
            text = str(f.get("text") or f.get("finding") or "").strip()
            step = str(f.get("step") or "").strip()
            url = str(f.get("doi_or_url") or f.get("url") or "").strip()
        else:
            text, step, url = str(f).strip(), "", ""
        hollow, _ = is_hollow_text(text, min_chars=16, min_unique_words=4)
        if hollow:
            hollow_n += 1
            continue
        raw_items.append({"text": text[:500], "step": step[:40], "doi_or_url": url[:500]})
    lines = [x["text"] for x in raw_items]
    uniq_lines, dupes = dedupe_findings(lines)
    uniq_set = set(uniq_lines)
    cleaned = [x for x in raw_items if x["text"] in uniq_set]
    # preserve order of first occurrence
    seen = set()
    ordered = []
    for x in cleaned:
        k = x["text"]
        if k in seen:
            continue
        seen.add(k)
        ordered.append(x)
    cleaned = ordered
    if len(cleaned) < thr["min_refute"]:
        return {
            "ok": False,
            "reason": (
                f"refute wake needs ≥{thr['min_refute']} unique substantial plan attacks "
                f"(got {len(cleaned)}; hollow={hollow_n}, dupes={dupes}) — no retreat on G thresholds"
            ),
            "view": state,
        }
    decision_u = str(decision or "HOLD").upper()
    if decision_u not in ("HOLD", "REOPEN", "KILL"):
        decision_u = "HOLD"
    state["refute"] = cleaned[:60]
    state["refute_status"] = decision_u
    state["updated_at"] = _utcnow()
    if decision_u in ("REOPEN", "KILL"):
        state["phase"] = "hunt" if decision_u == "KILL" else "draft"
        state["sealed"] = False
        return {
            "ok": False,
            "view": state,
            "status": decision_u,
            "reason": f"plan {decision_u} — return to hunt/draft; Seal blocked",
            "next": "Fix plan / re-hunt then draft + refute again",
        }
    state["phase"] = "seal"
    return {
        "ok": True,
        "view": state,
        "status": "HOLD",
        "next": "view_finalize — weaknesses-only report (no praise)",
    }


def finalize(state: Dict[str, Any], report: str) -> Dict[str, Any]:
    if state.get("refute_status") != "HOLD":
        return {
            "ok": False,
            "reason": "Cannot seal — refute wake must HOLD first",
            "view": state,
        }
    body = (report or "").strip()
    if len(body) < 200:
        return {"ok": False, "reason": "finalize report too short (<200 chars)", "view": state}
    if _PRAISE.search(body):
        return {
            "ok": False,
            "reason": "finalize contains praise/balanced language — weaknesses-only",
            "view": state,
        }
    # Must mention weaknesses / outcompete
    low = body.lower()
    if "weak" not in low and "fail" not in low and "gap" not in low and "risk" not in low:
        return {
            "ok": False,
            "reason": "finalize must discuss weaknesses/gaps/failures explicitly",
            "view": state,
        }
    state["sealed"] = True
    state["phase"] = "done"
    state["report"] = body[:20000]
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "view": state,
        "status": "sealed",
        "plan_steps": state.get("plan_steps"),
        "directive": "pass",
        "agent_role": {"may_propose_done": True, "may_decide_done": False},
        "next": "Plan sealed for research — use gk_meta.plan_validate with these steps before code modes",
    }


def view_ready_for_plan_validate(state: Dict[str, Any]) -> Tuple[bool, str]:
    if state.get("sealed") and state.get("refute_status") == "HOLD":
        return True, "view sealed"
    return False, "view campaign not sealed"
