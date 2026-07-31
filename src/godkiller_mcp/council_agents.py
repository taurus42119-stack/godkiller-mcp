"""Adversarial multi-agent council: Coder vs Hacker vs Optimizer via LLM + static evidence."""

from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List, Optional

from godkiller_mcp.llm_client import (
    ChatFn,
    load_llm_config,
    make_chat_fn,
    parse_agent_json,
)

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
    """Deterministic evidence pack fed into LLM agents (not the final verdict alone)."""
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
    severity = data.get("severity", 5)
    try:
        severity = int(severity)
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


class CouncilDebateEngine:
    """
    Real multi-agent debate:
      round1 independent LLM opinions (Coder/Hacker/Optimizer)
      round2 each agent revises after seeing the others
    Static AST evidence is attached as briefing, not the whole council.
    """

    def debate(
        self,
        proposed_code_or_plan: str,
        context: Optional[Dict[str, Any]] = None,
        *,
        require_llm: bool = True,
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
                if require_llm:
                    return {
                        "engine": "llm_multi_agent_council",
                        "error": (
                            "LLM council requires GODKILLER_LLM_API_KEY or OPENAI_API_KEY "
                            "(optional GODKILLER_LLM_BASE_URL / GODKILLER_LLM_MODEL). "
                            "Set require_llm=false only for static evidence preview."
                        ),
                        "llm_required": True,
                        "llm_configured": False,
                        "static_evidence": evidence,
                        "consensus_reached": False,
                        "verdict": "COUNCIL_BLOCKED_NO_LLM",
                    }
                # static-only preview
                consensus = all(evidence[r]["ok"] for r in ("coder", "hacker", "optimizer"))
                return {
                    "engine": "static_evidence_only",
                    "llm_required": False,
                    "llm_configured": False,
                    "static_evidence": evidence,
                    "consensus_reached": consensus,
                    "verdict": "STATIC_PASS" if consensus else "STATIC_REJECT",
                    "note": "Not a multi-agent debate — no LLM key configured.",
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

        approvals = sum(1 for v in current.values() if v["vote"] == "APPROVE")
        critical = any(v["vote"] == "REJECT" and v["severity"] >= 8 for v in current.values())
        # Security veto: hacker reject at severity>=7 blocks consensus
        hacker_veto = current["hacker"]["vote"] == "REJECT" and current["hacker"]["severity"] >= 7
        static_block = not evidence["hacker"]["ok"]
        consensus = (
            approvals == 3
            and not critical
            and not hacker_veto
            and not static_block
        )

        return {
            "engine": "llm_multi_agent_council",
            "llm_required": require_llm,
            "llm_configured": True,
            "model": getattr(cfg, "model", "injected_chat_fn") if cfg else "injected_chat_fn",
            "rounds": len(transcript),
            "static_evidence": evidence,
            "transcript": transcript,
            "final_opinions": current,
            "coder": current["coder"],
            "hacker": current["hacker"],
            "optimizer": current["optimizer"],
            "approvals": approvals,
            "hacker_veto": hacker_veto,
            "static_security_block": static_block,
            "consensus_reached": consensus,
            "verdict": "COUNCIL_PASS" if consensus else "COUNCIL_REJECT",
            "passes": {
                "coder": current["coder"]["vote"] == "APPROVE",
                "hacker": current["hacker"]["vote"] == "APPROVE" and not hacker_veto,
                "optimizer": current["optimizer"]["vote"] == "APPROVE",
                "static_security": evidence["hacker"]["ok"],
            },
        }
