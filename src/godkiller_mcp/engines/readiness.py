"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

class EpistemicConfidenceGate:
    """Edit readiness heuristic (NOT Bayesian). Named weights; require symbol or search hit."""

    W_FILE = 25.0
    W_AST = 25.0
    W_SYM = 20.0
    W_DEFS = 10.0
    W_SEARCH = 10.0
    W_HITS = 10.0
    W_SEARCH_FALLBACK = 5.0
    THRESHOLD = 70.0

    def evaluate(
        self,
        file_path: str,
        known_symbols: List[str],
        has_searched: bool = False,
        search_hit_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Client cannot attest search — ignore self-reported flags (theatre).
        client_search_ignored = bool(has_searched) or search_hit_count is not None
        has_searched = False
        search_hit_count = None

        pfile = Path(file_path)
        metrics: Dict[str, Any] = {
            "file_exists": pfile.exists(),
            "byte_size": 0,
            "ast_parse_ok": False,
            "def_count": 0,
            "class_count": 0,
            "symbol_hit_rate": 0.0,
            "symbols_requested": len(known_symbols or []),
            "symbols_found_in_file": 0,
            "search_done": False,
            "search_hit_count": None,
            "client_search_ignored": client_search_ignored,
        }
        reasons: List[str] = []
        if client_search_ignored:
            reasons.append(
                "ignored client has_searched/search_hit_count — not server evidence"
            )

        if not pfile.exists():
            return {
                "engine": "edit_readiness_metrics",
                "file": file_path,
                "metrics": metrics,
                "score": 0.0,
                "threshold": self.THRESHOLD,
                "allowed_to_edit": False,
                "missing": ["file_exists"],
                "reasons": ["File does not exist"],
                "recommendation": "BLOCK_EDIT_FORCE_RECON",
            }

        try:
            text = pfile.read_text(encoding="utf-8", errors="ignore")
            metrics["byte_size"] = len(text.encode("utf-8"))
            tree = ast.parse(text)
            metrics["ast_parse_ok"] = True
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    metrics["def_count"] += 1
                elif isinstance(node, ast.ClassDef):
                    metrics["class_count"] += 1
            found = 0
            for sym in known_symbols or []:
                if sym and sym in text:
                    found += 1
            metrics["symbols_found_in_file"] = found
            if known_symbols:
                metrics["symbol_hit_rate"] = found / max(len(known_symbols), 1)
            else:
                metrics["symbol_hit_rate"] = 0.0
        except SyntaxError as e:
            reasons.append(f"AST parse failed: {e}")
            metrics["ast_parse_ok"] = False
        except Exception as e:
            reasons.append(f"Read/analyze failed: {e}")

        score = 0.0
        if metrics["file_exists"]:
            score += self.W_FILE
        if metrics["ast_parse_ok"]:
            score += self.W_AST
        score += min(self.W_SYM, metrics["symbol_hit_rate"] * self.W_SYM)
        if metrics["def_count"] + metrics["class_count"] > 0:
            score += self.W_DEFS
        # Search weight only from in-file symbol proof (no client hit inflation)
        if float(metrics["symbol_hit_rate"] or 0) > 0:
            score += self.W_SEARCH_FALLBACK

        missing = []
        if not metrics["file_exists"]:
            missing.append("file_exists")
        if not metrics["ast_parse_ok"]:
            missing.append("ast_parse_ok")
        if known_symbols and metrics["symbol_hit_rate"] < 0.5:
            missing.append("symbol_hit_rate>=0.5")
        hit_ok = float(metrics["symbol_hit_rate"] or 0) > 0 or (
            not known_symbols
            and (metrics["def_count"] + metrics["class_count"]) > 0
        )
        if not hit_ok:
            missing.append("symbol_hit_rate>0_or_defs_present")

        allowed = score >= self.THRESHOLD and metrics["ast_parse_ok"] and hit_ok
        res: Dict[str, Any] = {
            "engine": "edit_readiness_metrics",
            "file": file_path,
            "metrics": metrics,
            "score": round(score, 2),
            "threshold": self.THRESHOLD,
            "weights": {
                "file": self.W_FILE,
                "ast": self.W_AST,
                "sym": self.W_SYM,
                "defs": self.W_DEFS,
                "search": self.W_SEARCH,
                "hits": self.W_HITS,
            },
            "allowed_to_edit": allowed,
            "missing": missing,
            "reasons": reasons,
            "recommendation": "PROCEED" if allowed else "BLOCK_EDIT_FORCE_RECON",
            "honest": (
                "edit readiness heuristic — not Bayesian / not formal verification; "
                "client search flags ignored"
            ),
            "readiness_score": round(score, 2),
        }
        from godkiller_mcp.view_propose import build_view_study_proposal, should_propose_view

        res["propose_view_study"] = should_propose_view(score)
        if res["propose_view_study"]:
            res["view_study"] = build_view_study_proposal(
                goal=f"edit readiness for {file_path}",
                confidence_pct=score,
                known_gaps=missing or reasons,
                topics=[
                    "similar file/module in a public reference repo",
                    "tests showing expected API for this path",
                ],
            )
            res["order"] = (
                "Confidence < 99%: IMMEDIATELY propose VIEW study (exemplar repos/files) "
                "to the user — do not silently invent the design. Call gk_mode.view_propose_study."
            )
        return res
