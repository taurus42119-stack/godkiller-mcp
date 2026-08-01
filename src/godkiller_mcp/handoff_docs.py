"""Handoff docs store: Planner-Builder-Evaluator spec and feedback protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from godkiller_mcp.path_sandbox import normalize_slug


class SpecFeedbackStore:
    def __init__(self, handoff_dir: str | Path):
        self.handoff_dir = Path(handoff_dir)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

    def _safe_slug(self, slug: str) -> str:
        return normalize_slug(slug)

    def _spec_path(self, slug: str) -> Path:
        safe = self._safe_slug(slug)
        path = (self.handoff_dir / f"{safe}_spec.json").resolve()
        path.relative_to(self.handoff_dir.resolve())
        return path

    def _feedback_path(self, slug: str) -> Path:
        safe = self._safe_slug(slug)
        path = (self.handoff_dir / f"{safe}_feedback.json").resolve()
        path.relative_to(self.handoff_dir.resolve())
        return path

    def require_spec(self, slug: str) -> Tuple[bool, str]:
        path = self._spec_path(slug)
        if not path.exists():
            return False, f"Spec missing for slug '{slug}'"
        return True, "Spec exists"

    def write_spec(
        self,
        slug: str,
        spec_md: str,
        goal: str = "",
        search_queries: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        queries = search_queries or []
        safe = self._safe_slug(slug)
        data = {
            "slug": safe,
            "spec_md": spec_md,
            "goal": goal,
            "search": {
                "count": len(queries),
                "queries": queries,
            },
            "search_queries": queries,
        }
        self._spec_path(safe).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def read_search_queries(self, slug: str) -> List[str]:
        path = self._spec_path(slug)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("search_queries") or data.get("search", {}).get("queries") or []
        except Exception:
            return []

    def write_feedback(
        self, slug: str, feedback_md: str, score: float = 1.0, passed: bool = True
    ) -> Dict[str, Any]:
        safe = self._safe_slug(slug)
        data = {
            "slug": safe,
            "feedback_md": feedback_md,
            "score": score,
            "passed": passed,
        }
        self._feedback_path(safe).write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data

    def require_passing_feedback(self, slug: str) -> Tuple[bool, str]:
        path = self._feedback_path(slug)
        if not path.exists():
            return False, f"Feedback missing for slug '{slug}'"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("passed", False):
                return True, "Feedback passed"
            return False, f"Feedback did not pass (score={data.get('score')})"
        except Exception as e:
            return False, str(e)

    def read_pack(self, slug: str) -> Dict[str, Any]:
        has_spec, _ = self.require_spec(slug)
        spec_md = ""
        if has_spec:
            spec_md = json.loads(self._spec_path(slug).read_text(encoding="utf-8")).get(
                "spec_md", ""
            )

        has_fb, _ = self.require_passing_feedback(slug)
        fb_md = ""
        if self._feedback_path(slug).exists():
            fb_md = json.loads(self._feedback_path(slug).read_text(encoding="utf-8")).get(
                "feedback_md", ""
            )

        return {
            "slug": slug,
            "has_spec": has_spec,
            "spec_md": spec_md,
            "has_passing_feedback": has_fb,
            "feedback_md": fb_md,
        }
