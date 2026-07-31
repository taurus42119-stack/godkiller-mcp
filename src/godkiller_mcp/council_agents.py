"""Adversarial council: host-IDE debate (default) + optional API multi-agent."""

from __future__ import annotations

import ast
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from godkiller_mcp.llm_client import (
    ChatFn,
    load_llm_config,
    make_chat_fn,
    parse_agent_json,
)

ROLES = ("coder", "hacker", "optimizer")

AGENT_PROMPTS = {
    "coder": (
        "You are CODER on an adversarial review council. Focus on correctness, "
        "API design, error handling, and whether the proposal actually solves the goal. "
        "Respond ONLY with JSON: "
        '{"vote":"APPROVE"|"REJECT","critique":"...","severity":0-10,"must_fix":["..."]}'
    ),
    "hacker": (
        "You are HACKER on an adversarial review council. Focus on injection, secrets, "
        "authz, unsafe deserialization, and exploitability. Be hostile. "
        "Respond ONLY with JSON: "
        '{"vote":"APPROVE"|"REJECT","critique":"...","severity":0-10,"must_fix":["..."]}'
    ),
    "optimizer": (
        "You are OPTIMIZER on an adversarial review council. Focus on complexity, "
        "hot paths, allocations, N+1, and maintainability cost. "
        "Respond ONLY with JSON: "
        '{"vote":"APPROVE"|"REJECT","critique":"...","severity":0-10,"must_fix":["..."]}'
    ),
}


def static_evidence(text: str) -> Dict[str, Any]:
    coder: Dict[str, Any] = {"role": "coder", "findings": [], "ok": True}
    hacker: Dict[str, Any] = {"role": "hacker", "findings": [], "ok": True}
    optimizer: Dict[str, Any] = {"role": "optimizer", "findings": [], "ok": True}

    security_rules = [
        (r"\beval\s*\(", "CWE-95 eval()"),
        (r"\bexec\s*\(", "CWE-95 exec()"),
        (r"shell\s*=\s*True", "CWE-78 shell=True"),
        (r"pickle\.loads\s*\(", "CWE-502 pickle.loads"),
        (r"yaml\.load\s*\([^,\)]*\)", "CWE-502 yaml.load without Loader"),
        (r"(password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]", "CWE-798 hardcoded secret"),
    ]
    for pat, label in security_rules:
        if re.search(pat, text, re.I):
            hacker["findings"].append(label)
            hacker["ok"] = False

    tree = None
    try:
        tree = ast.parse(text)
        coder["findings"].append("AST parse OK")
    except SyntaxError:
        coder["findings"].append("Not valid Python AST")
        if len(text.strip()) < 20:
            coder["ok"] = False
            coder["findings"].append("Proposal too short")

    if tree is not None:
        funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        tries = [n for n in ast.walk(tree) if isinstance(n, ast.Try)]
        coder["findings"].append(f"defs={len(funcs)} classes={len(classes)} try_blocks={len(tries)}")
        if funcs and len(tries) == 0 and any(
            "open(" in ast.dump(f) or "urlopen" in ast.dump(f) for f in funcs
        ):
            coder["findings"].append("I/O without try/except")
            coder["ok"] = False

        max_depth = 0

        def _depth(node: ast.AST, d: int = 0) -> None:
            nonlocal max_depth
            max_depth = max(max_depth, d)
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child,
                    (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.FunctionDef, ast.AsyncFunctionDef),
                ):
                    _depth(child, d + 1)
                else:
                    _depth(child, d)

        _depth(tree)
        long_funcs = []
        for f in funcs:
            try:
                span = (f.end_lineno or f.lineno) - f.lineno + 1
            except Exception:
                span = 0
            if span > 80:
                long_funcs.append(f"{f.name}:{span}L")
        optimizer["findings"].append(f"max_nesting_depth={max_depth}")
        if max_depth >= 6:
            optimizer["findings"].append("Deep nesting (>=6)")
            optimizer["ok"] = False
        if long_funcs:
            optimizer["findings"].append(f"Long functions: {long_funcs}")
            optimizer["ok"] = False

    return {"coder": coder, "hacker": hacker, "optimizer": optimizer}


def _normalize_vote(data: Dict[str, Any]) -> Dict[str, Any]:
    vote = str(data.get("vote", "REJECT")).upper().strip()
    if vote not in ("APPROVE", "REJECT"):
        vote = "REJECT"
    try:
        severity = int(data.get("severity", 5))
    except Exception:
        severity = 5
    severity = max(0, min(10, severity))
    return {
        "vote": vote,
        "critique": str(data.get("critique") or "")[:2000],
        "severity": severity,
        "must_fix": list(data.get("must_fix") or [])[:20],
        "raw": data,
    }


def tally_consensus(
    opinions: Dict[str, Dict[str, Any]],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    current = {r: opinions[r] for r in ROLES if r in opinions}
    missing = [r for r in ROLES if r not in current]
    if missing:
        return {
            "consensus_reached": False,
            "verdict": "COUNCIL_INCOMPLETE",
            "missing_roles": missing,
            "approvals": 0,
            "hacker_veto": False,
            "static_security_block": not evidence["hacker"]["ok"],
            "final_opinions": current,
            "coder": current.get("coder"),
            "hacker": current.get("hacker"),
            "optimizer": current.get("optimizer"),
            "passes": {},
        }

    approvals = sum(1 for v in current.values() if v["vote"] == "APPROVE")
    critical = any(v["vote"] == "REJECT" and v["severity"] >= 8 for v in current.values())
    hacker_veto = current["hacker"]["vote"] == "REJECT" and current["hacker"]["severity"] >= 7
    static_block = not evidence["hacker"]["ok"]
    consensus = approvals == 3 and not critical and not hacker_veto and not static_block
    return {
        "consensus_reached": consensus,
        "verdict": "COUNCIL_PASS" if consensus else "COUNCIL_REJECT",
        "missing_roles": [],
        "approvals": approvals,
        "hacker_veto": hacker_veto,
        "static_security_block": static_block,
        "final_opinions": current,
        "coder": current["coder"],
        "hacker": current["hacker"],
        "optimizer": current["optimizer"],
        "passes": {
            "coder": current["coder"]["vote"] == "APPROVE",
            "hacker": current["hacker"]["vote"] == "APPROVE" and not hacker_veto,
            "optimizer": current["optimizer"]["vote"] == "APPROVE",
            "static_security": evidence["hacker"]["ok"],
        },
    }


@dataclass
class HostCouncilSession:
    session_id: str
    proposal: str
    context: Dict[str, Any]
    evidence: Dict[str, Any]
    round: int = 1
    max_rounds: int = 2
    opinions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    transcript: List[Dict[str, Any]] = field(default_factory=list)


_HOST_SESSIONS: Dict[str, HostCouncilSession] = {}


class CouncilDebateEngine:
    """
    Modes:
      - host (default without API key): IDE model plays Coder/Hacker/Optimizer, MCP tallies
      - api: server-side OpenAI-compatible multi-round debate when key present / mode=api
    """

    def resolve_mode(self, mode: Optional[str] = None, prefer_api: bool = False) -> str:
        m = (mode or "auto").lower().strip()
        if m in ("host", "api"):
            return m
        # auto
        if prefer_api and load_llm_config() is not None:
            return "api"
        if load_llm_config() is not None and prefer_api:
            return "api"
        return "host"

    def start_host(
        self,
        proposed_code_or_plan: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        max_rounds: int = 2,
    ) -> Dict[str, Any]:
        text = proposed_code_or_plan or ""
        evidence = static_evidence(text)
        sid = f"council_{uuid.uuid4().hex[:10]}"
        session = HostCouncilSession(
            session_id=sid,
            proposal=text,
            context=context or {},
            evidence=evidence,
            max_rounds=max(1, int(max_rounds)),
        )
        _HOST_SESSIONS[sid] = session

        scripts = []
        for role in ROLES:
            scripts.append(
                {
                    "role": role,
                    "system": AGENT_PROMPTS[role],
                    "user_brief": (
                        f"Play ONLY the {role.upper()} seat for this council round {session.round}. "
                        "Do not speak for other roles. Return JSON vote fields only.\n\n"
                        f"PROPOSAL:\n{text[:8000]}\n\n"
                        f"STATIC_EVIDENCE:\n{json.dumps(evidence, indent=2)[:4000]}\n\n"
                        f"CONTEXT:\n{json.dumps(context or {}, indent=2)[:2000]}"
                    ),
                }
            )

        return {
            "engine": "host_multi_agent_council",
            "mode": "host",
            "phase": "awaiting_opinions",
            "session_id": sid,
            "round": session.round,
            "max_rounds": session.max_rounds,
            "roles_required": list(ROLES),
            "missing_roles": list(ROLES),
            "static_evidence": evidence,
            "agent_scripts": scripts,
            "instructions": (
                "For each role in agent_scripts: adopt that system prompt, answer user_brief, "
                "then call gk_code council_submit with session_id, role, vote, critique, severity. "
                "When all three roles are in, call council_finalize (or submit again for round 2 if asked)."
            ),
            "consensus_reached": False,
            "verdict": "COUNCIL_IN_PROGRESS",
        }

    def submit_opinion(
        self,
        session_id: str,
        role: str,
        vote: str,
        critique: str = "",
        severity: int = 5,
        must_fix: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        session = _HOST_SESSIONS.get(session_id)
        if not session:
            return {"error": f"Unknown council session_id: {session_id}", "verdict": "COUNCIL_ERROR"}
        role = (role or "").lower().strip()
        if role not in ROLES:
            return {"error": f"Invalid role {role}; need one of {ROLES}", "verdict": "COUNCIL_ERROR"}

        session.opinions[role] = _normalize_vote(
            {
                "vote": vote,
                "critique": critique,
                "severity": severity,
                "must_fix": must_fix or [],
            }
        )
        # Block hollow REJECT theatre at submit time
        norm = session.opinions[role]
        if str(norm.get("vote") or "").upper() == "REJECT":
            from godkiller_mcp.claim_armor import _substantial_hacker_reject

            if not _substantial_hacker_reject(norm):
                del session.opinions[role]
                return {
                    "error": (
                        "Hacker/role REJECT rejected as theatre: need non-hollow critique "
                        "(≥24 chars), ≥1 substantial must_fix, severity≥5"
                    ),
                    "verdict": "COUNCIL_ERROR",
                    "session_id": session_id,
                    "role": role,
                }
        missing = [r for r in ROLES if r not in session.opinions]
        out: Dict[str, Any] = {
            "engine": "host_multi_agent_council",
            "mode": "host",
            "session_id": session_id,
            "round": session.round,
            "accepted_role": role,
            "roles_present": sorted(session.opinions.keys()),
            "missing_roles": missing,
            "phase": "awaiting_opinions" if missing else "ready_to_finalize_or_next_round",
        }
        if not missing:
            out["hint"] = (
                "All roles in for this round. Call council_finalize to tally, "
                "or submit revised opinions after reviewing others (round 2)."
            )
            out["others_for_debate"] = {
                r: session.opinions[r] for r in ROLES if r != role
            }
        return out

    def finalize_host(self, session_id: str, *, advance_round: bool = False) -> Dict[str, Any]:
        session = _HOST_SESSIONS.get(session_id)
        if not session:
            return {"error": f"Unknown council session_id: {session_id}", "verdict": "COUNCIL_ERROR"}

        if advance_round and session.round < session.max_rounds:
            # freeze current opinions into transcript, clear for next round
            session.transcript.append({"round": session.round, "opinions": dict(session.opinions)})
            session.round += 1
            session.opinions = {}
            scripts = []
            prev = session.transcript[-1]["opinions"]
            for role in ROLES:
                others = {k: v for k, v in prev.items() if k != role}
                scripts.append(
                    {
                        "role": role,
                        "system": AGENT_PROMPTS[role],
                        "user_brief": (
                            f"Round {session.round} debate. Revise your vote after seeing others.\n"
                            f"PROPOSAL:\n{session.proposal[:8000]}\n\n"
                            f"OTHERS:\n{json.dumps(others, indent=2)[:6000]}\n"
                            f"YOUR PREVIOUS:\n{json.dumps(prev.get(role, {}), indent=2)[:2000]}"
                        ),
                    }
                )
            return {
                "engine": "host_multi_agent_council",
                "mode": "host",
                "phase": "awaiting_opinions",
                "session_id": session_id,
                "round": session.round,
                "max_rounds": session.max_rounds,
                "agent_scripts": scripts,
                "transcript": session.transcript,
                "missing_roles": list(ROLES),
                "verdict": "COUNCIL_IN_PROGRESS",
                "instructions": "Submit all three roles again for this round, then finalize.",
            }

        tallied = tally_consensus(session.opinions, session.evidence)
        if tallied["verdict"] == "COUNCIL_INCOMPLETE":
            return {
                "engine": "host_multi_agent_council",
                "mode": "host",
                "session_id": session_id,
                "round": session.round,
                **tallied,
            }

        session.transcript.append({"round": session.round, "opinions": dict(session.opinions)})
        result = {
            "engine": "host_multi_agent_council",
            "mode": "host",
            "session_id": session_id,
            "rounds": len(session.transcript),
            "static_evidence": session.evidence,
            "transcript": session.transcript,
            **tallied,
        }
        # keep session for inspection; optional cleanup
        return result

    def debate_api(
        self,
        proposed_code_or_plan: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        chat_fn: Optional[ChatFn] = None,
        rounds: int = 2,
    ) -> Dict[str, Any]:
        context = context or {}
        text = proposed_code_or_plan or ""
        evidence = static_evidence(text)

        cfg = None
        if chat_fn is None:
            cfg = load_llm_config()
            if cfg is None:
                return {
                    "engine": "llm_multi_agent_council",
                    "mode": "api",
                    "error": "API mode needs GODKILLER_LLM_API_KEY or OPENAI_API_KEY",
                    "llm_configured": False,
                    "fallback": "host",
                    "consensus_reached": False,
                    "verdict": "COUNCIL_BLOCKED_NO_LLM",
                }
            chat_fn = make_chat_fn(cfg)

        briefing = {
            "proposal": text[:12000],
            "context": context,
            "static_evidence": evidence,
        }
        user_r1 = (
            "Review this proposal. Use static_evidence as hints, but form your own judgment.\n"
            + json.dumps(briefing, indent=2)[:14000]
        )

        round1: Dict[str, Any] = {}
        for role, system in AGENT_PROMPTS.items():
            raw = chat_fn(system, user_r1)
            round1[role] = _normalize_vote(parse_agent_json(raw))

        transcript: List[Dict[str, Any]] = [{"round": 1, "opinions": round1}]
        current = round1

        for r in range(2, max(2, rounds) + 1):
            revised: Dict[str, Any] = {}
            for role, system in AGENT_PROMPTS.items():
                others = {k: v for k, v in current.items() if k != role}
                user_r = (
                    f"Round {r} debate. Here are the other agents' opinions. "
                    "Revise your vote if warranted. Respond JSON only.\n"
                    f"PROPOSAL:\n{text[:8000]}\n\nOTHERS:\n{json.dumps(others, indent=2)[:8000]}\n"
                    f"YOUR PREVIOUS:\n{json.dumps(current[role], indent=2)[:2000]}"
                )
                raw = chat_fn(system, user_r)
                revised[role] = _normalize_vote(parse_agent_json(raw))
            transcript.append({"round": r, "opinions": revised})
            current = revised

        tallied = tally_consensus(current, evidence)
        return {
            "engine": "llm_multi_agent_council",
            "mode": "api",
            "llm_configured": True,
            "model": getattr(cfg, "model", "injected_chat_fn") if cfg else "injected_chat_fn",
            "rounds": len(transcript),
            "static_evidence": evidence,
            "transcript": transcript,
            **tallied,
        }

    def debate(
        self,
        proposed_code_or_plan: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        mode: Optional[str] = None,
        prefer_api: bool = False,
        require_llm: bool = False,
        chat_fn: Optional[ChatFn] = None,
        rounds: int = 2,
    ) -> Dict[str, Any]:
        """
        Entry point.
        Default: host session (IDE plays roles).
        mode=api or prefer_api with key: server-side LLM debate.
        require_llm=True forces api and errors without key (legacy strict).
        """
        if require_llm:
            resolved = "api"
        else:
            resolved = self.resolve_mode(mode, prefer_api=prefer_api)

        if resolved == "api" or chat_fn is not None:
            if chat_fn is None and load_llm_config() is None and not require_llm:
                # soft fallback to host
                return self.start_host(proposed_code_or_plan, context, max_rounds=rounds)
            return self.debate_api(
                proposed_code_or_plan,
                context,
                chat_fn=chat_fn,
                rounds=rounds,
            )
        return self.start_host(proposed_code_or_plan, context, max_rounds=rounds)
