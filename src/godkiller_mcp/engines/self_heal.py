"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.engines.log_trace import LogTraceEngine


class SelfHealingEngine:
    """
    Failure recovery: parse traceback structure, map tool→fallback, optionally run it.

    Not magic auto-repair. Diagnose is structured (frames / exception / path existence),
    then one explicit fallback tool is executed when an executor is provided.
    """

    # Explicit tool routing — not a free-form substring soup.
    _TOOL_FALLBACK = {
        "godkiller_hyper_search": "godkiller_ast_grep",
        "ripgrep": "godkiller_ast_grep",
        "godkiller_fast_find": "godkiller_repo_map",
        "godkiller_ast_grep": "godkiller_repo_map",
        "godkiller_context_preview": "godkiller_exhaustive_read",
    }

    def _parse_traceback(self, text: str) -> Dict[str, Any]:
        return LogTraceEngine().parse_log(text or "")

    def _existing_frame_files(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        checked = []
        for fr in frames[:12]:
            path = fr.get("file") or ""
            exists = bool(path) and Path(path).is_file()
            checked.append({**fr, "exists_on_disk": exists})
        return checked

    def diagnose(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        task_context = task_context or {}
        raw = error_or_output or ""
        parsed = self._parse_traceback(raw)
        frames = self._existing_frame_files(parsed.get("stack_frames") or [])
        missing_frames = [f for f in frames if not f.get("exists_on_disk")]
        exc = parsed.get("exception_type") or "UnknownException"
        msg = (parsed.get("message") or "").strip()

        signals = {
            "exception_type": exc,
            "message": msg[:300],
            "frame_count": len(frames),
            "missing_frame_files": len(missing_frames),
            "failed_tool": failed_tool,
            "has_traceback_frames": bool(frames),
        }

        # 1) Structured traceback → parse frames (always preferred when frames exist)
        if frames or exc not in ("UnknownException",) and "Error" in exc:
            return {
                "diagnosis": (
                    f"Structured traceback: {exc}: {msg[:120]} "
                    f"({len(frames)} frame(s), {len(missing_frames)} missing on disk)."
                ),
                "recommended_tool": "godkiller_log_trace",
                "remediated_args": {"log_output": raw},
                "signals": signals,
                "frames": frames,
                "method": "traceback_parse",
            }

        # 2) Explicit missing path in context
        candidate = task_context.get("path") or task_context.get("file_path")
        if candidate and not Path(str(candidate)).exists():
            return {
                "diagnosis": f"Path missing on disk: {candidate}",
                "recommended_tool": "godkiller_repo_map",
                "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
                "signals": {**signals, "missing_path": str(candidate)},
                "method": "path_exists_check",
            }

        # 3) Known tool failure → fixed fallback map
        if failed_tool in self._TOOL_FALLBACK:
            fb = self._TOOL_FALLBACK[failed_tool]
            if fb == "godkiller_ast_grep":
                args = {
                    "pattern": task_context.get("pattern", "def $FUNC($$$ARGS)"),
                    "search_path": task_context.get("search_path", "."),
                }
            elif fb == "godkiller_exhaustive_read":
                args = {"dir_path": task_context.get("dir_path") or task_context.get("root_dir", ".")}
            else:
                args = {"root_dir": task_context.get("root_dir", ".")}
            return {
                "diagnosis": f"Tool '{failed_tool}' failed; explicit fallback '{fb}'.",
                "recommended_tool": fb,
                "remediated_args": args,
                "signals": signals,
                "method": "tool_fallback_map",
            }

        # 4) OS-level missing file language in message (last resort, after structure)
        low = raw.lower()
        if "no such file" in low or "filenotfounderror" in low or "errno 2" in low:
            return {
                "diagnosis": "FileNotFound-class failure; remap repository.",
                "recommended_tool": "godkiller_repo_map",
                "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
                "signals": signals,
                "method": "filenotfound_signal",
            }

        return {
            "diagnosis": "No structured traceback or known tool map hit; remap before retry.",
            "recommended_tool": "godkiller_repo_map",
            "remediated_args": {"root_dir": task_context.get("root_dir", ".")},
            "signals": signals,
            "method": "default_remap",
        }

    def heal(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        plan = self.diagnose(failed_tool, error_or_output, task_context)
        return {
            "engine": "self_heal_executor",
            "tier": "recovery",
            "action": "SUGGEST_AND_OPTIONAL_RUN",
            "executed": False,
            **plan,
        }

    async def heal_and_run(
        self,
        failed_tool: str,
        error_or_output: str,
        task_context: Optional[Dict[str, Any]] = None,
        executor: Any = None,
    ) -> Dict[str, Any]:
        plan = self.diagnose(failed_tool, error_or_output, task_context)
        out: Dict[str, Any] = {
            "engine": "self_heal_executor",
            "tier": "recovery",
            "action": "EXECUTED_FALLBACK" if executor else "SUGGEST_ONLY",
            **plan,
            "executed": False,
        }
        if executor is None:
            return out
        raw = await executor(plan["recommended_tool"], plan["remediated_args"])
        if isinstance(raw, list) and raw and hasattr(raw[0], "text"):
            try:
                out["fallback_output"] = json.loads(raw[0].text)
            except Exception:
                out["fallback_output"] = raw[0].text
        else:
            out["fallback_output"] = raw
        out["executed"] = True
        # Confirm heal produced structured output when we routed to log_trace
        if plan.get("recommended_tool") == "godkiller_log_trace" and isinstance(
            out.get("fallback_output"), dict
        ):
            out["heal_verified"] = bool(out["fallback_output"].get("exception_type"))
        else:
            out["heal_verified"] = out["executed"]
        return out
