"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import graphlib
import json
from typing import Any, Dict, List



class PipelineRunner:
    """DAG executor that actually invokes tool handlers (not dry-run mark-success)."""

    async def run_pipeline(
        self,
        steps: List[Dict[str, Any]],
        executor: Any = None,
    ) -> Dict[str, Any]:
        """
        executor: async callable(tool_name: str, args: dict) -> list|dict|str
        If omitted, returns planned order only (explicit dry_run).
        """
        results = []
        pipeline_context: Dict[str, Any] = {}

        graph = {}
        for idx, step in enumerate(steps):
            deps = step.get("depends_on", [])
            graph[idx] = set(deps)

        try:
            ts = graphlib.TopologicalSorter(graph)
            order = list(ts.static_order())
        except Exception as e:
            return {"error": f"Invalid DAG structure: {e}", "engine": "pipeline_executor"}

        if executor is None:
            return {
                "engine": "pipeline_executor",
                "dry_run": True,
                "note": "No executor provided — steps not run. Pass MCP handle_tool as executor.",
                "total_steps": len(steps),
                "execution_order": order,
                "results": [
                    {"step": i, "name": steps[i].get("name", "unknown"), "status": "planned_not_executed"}
                    for i in order
                ],
            }

        for step_idx in order:
            step = steps[step_idx]
            name = step.get("name") or step.get("tool") or "unknown"
            args = dict(step.get("args") or {})

            for k, v in list(args.items()):
                if isinstance(v, str) and v.startswith("$"):
                    ctx_key = v[1:]
                    if ctx_key in pipeline_context:
                        args[k] = pipeline_context[ctx_key]

            try:
                raw = await executor(name, args)
                if isinstance(raw, list) and raw and hasattr(raw[0], "text"):
                    body = raw[0].text
                    try:
                        parsed = json.loads(body)
                    except Exception:
                        parsed = body
                else:
                    parsed = raw
                status = "success"
                if isinstance(parsed, dict) and parsed.get("error"):
                    status = "error"
                step_result = {
                    "step": step_idx,
                    "name": name,
                    "status": status,
                    "args": args,
                    "output": parsed,
                }
            except Exception as exc:
                step_result = {
                    "step": step_idx,
                    "name": name,
                    "status": "error",
                    "args": args,
                    "error": str(exc),
                }
                if step.get("stop_on_error", True):
                    pipeline_context[f"step_{step_idx}_output"] = step_result
                    results.append(step_result)
                    return {
                        "engine": "pipeline_executor",
                        "dry_run": False,
                        "total_steps": len(steps),
                        "execution_order": order,
                        "results": results,
                        "aborted_at": step_idx,
                    }

            pipeline_context[f"step_{step_idx}_output"] = step_result
            results.append(step_result)

        return {
            "engine": "pipeline_executor",
            "dry_run": False,
            "total_steps": len(steps),
            "execution_order": order,
            "results": results,
            "all_ok": all(r.get("status") == "success" for r in results),
        }
