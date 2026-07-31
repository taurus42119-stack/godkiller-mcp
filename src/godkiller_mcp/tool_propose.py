"""Tool propose — search≠install; approve≠use; claim needs used or reject_all.

Pessimistic capability expansion: agent proposes 5–10 public candidates after host
search; human/host approves; MCP never silent-installs packages.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from godkiller_mcp.evidence_quality import cite_source_ok, is_hollow_text
from godkiller_mcp.ship_mode import env_disables, relax_enabled

_META_KEY = "tool_propose"
_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_state(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = (meta or {}).get(_META_KEY) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def propose_enabled() -> bool:
    """Default ON. Kill-switch only under relax (ship ignores =0)."""
    if env_disables("GODKILLER_TOOL_PROPOSE"):
        return False
    # Explicit off without relax still ignored in ship via env_disables;
    # if unset, on.
    return True


def _norm_candidate(raw: Any, *, idx: int) -> Tuple[Optional[Dict[str, Any]], str]:
    if not isinstance(raw, dict):
        return None, f"candidate[{idx}] must be object"
    name = str(raw.get("name") or "").strip()
    url = str(raw.get("url") or "").strip()
    reason = str(raw.get("reason") or "").strip()
    risk = str(raw.get("risk") or "").strip() or "unvetted third-party tool"
    version = str(raw.get("version") or "").strip()
    kind = str(raw.get("kind") or "other").strip().lower() or "other"
    cid = str(raw.get("id") or f"c{idx + 1}").strip()
    if not _ID_RE.match(cid):
        return None, f"candidate[{idx}] bad id"
    if len(name) < 2:
        return None, f"candidate[{idx}] name too short"
    ok_s, why_s = cite_source_ok(url)
    if not ok_s:
        return None, f"candidate[{idx}] url: {why_s}"
    from godkiller_mcp.ssrf import assert_public_url

    ok_u, why_u = assert_public_url(url, resolve=False)
    if not ok_u:
        return None, f"candidate[{idx}] ssrf: {why_u}"
    hollow, why_h = is_hollow_text(reason, min_chars=20, min_unique_words=4)
    if hollow:
        return None, f"candidate[{idx}] reason hollow: {why_h}"
    if len(risk) < 3:
        return None, f"candidate[{idx}] risk required"
    install_hint = str(raw.get("install_hint") or "").strip()
    if not install_hint:
        # Suggest only — never execute
        if "pypi.org" in url.lower() or kind in ("pip", "pypi", "python"):
            install_hint = f"pip install {name}"
        elif "npmjs.com" in url.lower() or kind in ("npm", "node"):
            install_hint = f"npm install {name}"
        else:
            install_hint = f"Host-install manually from {url} (MCP will not install)"
    return {
        "id": cid,
        "name": name[:200],
        "url": url[:1000],
        "reason": reason[:800],
        "risk": risk[:400],
        "version": version[:80],
        "kind": kind[:40],
        "install_hint": install_hint[:400],
        "excerpt": str(raw.get("excerpt") or "")[:2000],
    }, "ok"


def propose(
    need: str,
    candidates: Sequence[Any],
    *,
    min_n: int = 5,
    max_n: int = 10,
    workspace: str = ".",
    task_id: str = "",
) -> Dict[str, Any]:
    need = (need or "").strip()
    hollow_n, why_n = is_hollow_text(need, min_chars=12, min_unique_words=3)
    if hollow_n:
        return {"ok": False, "reason": f"need hollow: {why_n}"}

    min_n = max(5, int(min_n or 5))
    max_n = min(10, max(min_n, int(max_n or 10)))
    if not isinstance(candidates, (list, tuple)):
        return {"ok": False, "reason": "candidates must be a list"}
    if len(candidates) < min_n:
        return {
            "ok": False,
            "reason": f"need ≥{min_n} candidates (got {len(candidates)}) — host-search then propose",
        }
    if len(candidates) > max_n:
        return {"ok": False, "reason": f"max {max_n} candidates (got {len(candidates)})"}

    cleaned: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for i, raw in enumerate(candidates):
        c, why = _norm_candidate(raw, idx=i)
        if c is None:
            return {"ok": False, "reason": why}
        if c["id"] in seen_ids:
            return {"ok": False, "reason": f"duplicate id {c['id']}"}
        if c["url"].lower() in seen_urls:
            return {"ok": False, "reason": f"duplicate url {c['url']}"}
        seen_ids.add(c["id"])
        seen_urls.add(c["url"].lower())
        cleaned.append(c)

    state = {
        "need": need[:1000],
        "candidates": cleaned,
        "status": "proposed",
        "approved_ids": [],
        "used_ids": [],
        "reject_reason": "",
        "workspace": str(Path(workspace).resolve()),
        "task_id": task_id,
        "updated_at": _utcnow(),
        "honest": "search≠install; approve≠use; host installs outside MCP",
    }
    return {
        "ok": True,
        "source": "tool_propose",
        "server_authored": True,
        "tool_propose": state,
        "count": len(cleaned),
        "next": "tool_approve(ids=[...]) OR tool_reject_all(reason=...) — never silent install",
    }


def enrich_scrape(state: Dict[str, Any], ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Optional: scrape public pages for excerpts. Never installs."""
    cands = list(state.get("candidates") or [])
    want = set(ids) if ids else {c.get("id") for c in cands}
    try:
        from godkiller_mcp.code_intel import DeepScrapeEngine

        engine = DeepScrapeEngine()
    except Exception as exc:
        return {"ok": False, "reason": f"scrape unavailable: {exc}", "tool_propose": state}

    updated = 0
    for c in cands:
        if c.get("id") not in want:
            continue
        url = c.get("url") or ""
        try:
            out = engine.scrape(url, max_length=1200)
            if isinstance(out, dict) and out.get("markdown"):
                c["excerpt"] = str(out["markdown"])[:2000]
                updated += 1
            elif isinstance(out, dict) and out.get("error"):
                c["excerpt_error"] = str(out["error"])[:200]
        except Exception as exc:
            c["excerpt_error"] = str(exc)[:200]
    state["candidates"] = cands
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "source": "tool_propose",
        "server_authored": True,
        "enriched": updated,
        "tool_propose": state,
    }


def approve(state: Dict[str, Any], ids: Sequence[str], *, workspace: str = "") -> Dict[str, Any]:
    if state.get("status") not in ("proposed", "approved"):
        return {"ok": False, "reason": f"cannot approve from status={state.get('status')}"}
    known = {c.get("id") for c in state.get("candidates") or []}
    pick = [str(i).strip() for i in ids if str(i).strip()]
    if not pick:
        return {"ok": False, "reason": "approve requires ≥1 id"}
    bad = [i for i in pick if i not in known]
    if bad:
        return {"ok": False, "reason": f"unknown ids: {bad}"}
    state["approved_ids"] = pick
    state["status"] = "approved"
    state["reject_reason"] = ""
    state["updated_at"] = _utcnow()

    ws = Path(workspace or state.get("workspace") or ".").resolve()
    hint_path = _write_allow_hint(ws, state)

    return {
        "ok": True,
        "source": "tool_approve",
        "server_authored": True,
        "tool_propose": state,
        "hint_path": str(hint_path),
        "honest": "Copied install hints only — host must install; then tool_used",
        "next": "Host install outside MCP → tool_used(proposal_id, how=...)",
    }


def reject_all(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
    if not state.get("candidates"):
        return {"ok": False, "reason": "call tool_propose first"}
    hollow, why = is_hollow_text(reason, min_chars=40, min_unique_words=8)
    if hollow:
        return {"ok": False, "reason": f"reject_all reason hollow: {why}"}
    state["status"] = "rejected_sufficient"
    state["approved_ids"] = []
    state["reject_reason"] = (reason or "").strip()[:1200]
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "source": "tool_approve",
        "server_authored": True,
        "tool_propose": state,
        "next": "Existing tools claimed sufficient — other claim gates still apply",
    }


def record_used(state: Dict[str, Any], proposal_id: str, how: str) -> Dict[str, Any]:
    if state.get("status") != "approved":
        return {"ok": False, "reason": "tool_used requires prior approve"}
    pid = str(proposal_id or "").strip()
    if pid not in (state.get("approved_ids") or []):
        return {"ok": False, "reason": f"{pid} not in approved_ids"}
    hollow, why = is_hollow_text(how, min_chars=16, min_unique_words=4)
    if hollow:
        return {"ok": False, "reason": f"how hollow: {why}"}
    used = list(state.get("used_ids") or [])
    entry = {"id": pid, "how": how.strip()[:800], "at": _utcnow()}
    # replace prior how for same id
    used = [u for u in used if isinstance(u, dict) and u.get("id") != pid]
    used.append(entry)
    state["used_ids"] = used
    state["updated_at"] = _utcnow()
    return {
        "ok": True,
        "source": "tool_used",
        "server_authored": True,
        "tool_propose": state,
        "entry": entry,
    }


def _write_allow_hint(workspace: Path, state: Dict[str, Any]) -> Path:
    root = workspace / ".godkiller"
    root.mkdir(parents=True, exist_ok=True)
    path = root / "tool_allow.json"
    approved = set(state.get("approved_ids") or [])
    tools = [c for c in (state.get("candidates") or []) if c.get("id") in approved]
    payload = {
        "workspace": str(workspace),
        "need": state.get("need"),
        "approved": tools,
        "install_commands": [t.get("install_hint") for t in tools],
        "honest": "HINT ONLY — GODKILLER does not run these commands",
        "at": _utcnow(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def status_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ok": True,
        "source": "tool_propose_status",
        "server_authored": True,
        "tool_propose": state or {},
        "gate_preview": claim_tool_propose_gate_from_meta({"tool_propose": state}),
    }


def claim_tool_propose_gate_from_meta(meta: Optional[Dict[str, Any]]) -> Tuple[bool, str]:
    return claim_tool_propose_gate_state(get_state(meta), mode=(meta or {}).get("mode"))


def claim_tool_propose_gate_state(
    tp: Dict[str, Any],
    *,
    mode: Any = None,
) -> Tuple[bool, str]:
    if not propose_enabled():
        return True, "tool_propose skipped (relax kill-switch)"
    if str(mode or "").strip().lower() == "ask":
        return True, "tool_propose N/A for ask"

    if not tp or not (tp.get("candidates") or []):
        return (
            False,
            "Forced tool_propose: host-search → propose 5–10 public candidates "
            "(gk_mode.tool_propose) before exit/claim — search≠install",
        )
    status = str(tp.get("status") or "")
    if status == "proposed":
        return (
            False,
            "tool_propose pending decision: tool_approve(ids) OR tool_reject_all(reason)",
        )
    if status == "rejected_sufficient":
        reason = str(tp.get("reject_reason") or "")
        hollow, why = is_hollow_text(reason, min_chars=40, min_unique_words=8)
        if hollow:
            return False, f"reject_all reason hollow: {why}"
        return True, "tool_propose reject_all (existing tools sufficient)"
    if status == "approved":
        approved = list(tp.get("approved_ids") or [])
        if not approved:
            return False, "approved status but empty approved_ids"
        used_ids = {
            u.get("id")
            for u in (tp.get("used_ids") or [])
            if isinstance(u, dict) and u.get("id")
        }
        missing = [i for i in approved if i not in used_ids]
        if missing:
            return (
                False,
                f"approved tools missing tool_used evidence: {missing} "
                "(host install then gk_mode.tool_used)",
            )
        return True, f"tool_propose used OK ({len(approved)})"
    return False, f"tool_propose unknown status={status}"


def claim_tool_propose_gate(state) -> Tuple[bool, str]:
    """Claim/exit gate — additive over skill/search/verify."""
    if relax_enabled() and os.environ.get("GODKILLER_TOOL_PROPOSE", "1").strip().lower() in (
        "0",
        "false",
        "off",
        "no",
    ):
        return True, "tool_propose skipped (relax)"
    if not propose_enabled():
        return True, "tool_propose skipped (relax kill-switch)"

    meta = getattr(getattr(state, "handle", None), "metadata", None) or {}
    mode = meta.get("mode")
    # Prefer sealed evidence if present
    tp = get_state(meta)
    try:
        for ev in reversed(getattr(state, "evidence", None) or []):
            payload = getattr(ev, "payload", None) or {}
            if payload.get("source") in ("tool_propose", "tool_approve", "tool_used") and payload.get(
                "tool_propose"
            ):
                tp = dict(payload["tool_propose"])
                break
    except Exception:
        pass
    return claim_tool_propose_gate_state(tp, mode=mode)
