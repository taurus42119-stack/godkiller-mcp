"""GODKILLER MCP Server — slim facade surface (~12 tools) over legacy dispatch."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer

from godkiller_mcp.dispatch import handle_tool, router

app = MCPServer(
    name="GODKILLER",
    version="1.3.0",
    instructions=(
        "Antigravity phase/evidence orchestrator. Prefer gk_phase + gk_meta.plan_validate "
        "before edits; gk_verify.bundle before claim_done."
    ),
)

# Facade name -> { action -> legacy tool name }
FACADE_ACTIONS: Dict[str, Dict[str, str]] = {
    "gk_route": {"classify": "godkiller_route_intent"},
    "gk_task": {
        "open": "open_task",
        "hypothesize": "propose_hypothesis",
        "graph": "get_task_graph",
        "policy": "policy_decide",
        "failing_slice": "get_failing_slice",
        "blast_radius": "blast_radius",
        "edit_safe": "check_edit_safe",
    },
    "gk_phase": {
        "assert": "assert_phase",
        "claim_done": "request_claim_done",
        "rubric": "evaluate_rubric",
    },
    "gk_evidence": {
        "submit": "submit_evidence",
        "capture_shot": "capture_shot",
        "visual_critic": "visual_critic",
        "screenshot": "register_screenshot",
        "journey": "register_ui_journey",
        "inspect_image": "godkiller_inspect_image",
    },
    "gk_verify": {
        "bundle": "verify_bundle",
        "soak": "soak_run",
        "loop_record": "record_tool_event",
        "loop_status": "loop_status",
        "competitor": "competitor_scan",
        "compare": "compare_delta",
        "ladder": "set_ambition_ladder",
    },
    "gk_memory": {
        "ingest_lesson": "ingest_lesson",
        "retrieve": "retrieve_lessons",
        "retrieve_verified": "retrieve_lessons_verified",
        "marathon_init": "marathon_init",
        "marathon_load": "marathon_load_progress",
        "marathon_save": "marathon_save_progress",
        "marathon_search_gate": "marathon_search_gate",
        "marathon_wake": "marathon_next_wake",
        "marathon_list": "marathon_list",
        "query_graph": "gk_memory_query_graph",
        "what_blocked": "gk_memory_what_blocked",
        "upsert_episode": "gk_memory_upsert_episode",
    },
    "gk_code": {
        "map": "godkiller_repo_map",
        "search": "godkiller_hyper_search",
        "find": "godkiller_fast_find",
        "preview": "godkiller_context_preview",
        "read_all": "godkiller_exhaustive_read",
        "ast_grep": "godkiller_ast_grep",
        "auto_fix": "godkiller_auto_fix",
        "pipeline": "godkiller_pipeline",
        "self_heal": "godkiller_self_heal",
        "confidence": "godkiller_confidence_check",
        "scrape": "godkiller_deep_scrape",
        "log_trace": "godkiller_log_trace",
        "council": "godkiller_council_debate",
        "skillify": "godkiller_auto_skillify",
        "read_full": "gk_code_read_full",
    },
    "gk_scan": {
        "security": "godkiller_security_scan",
        "semgrep": "gk_scan_semgrep",
    },
    "gk_browser": {
        "navigate": "gk_browser_navigate",
        "snapshot": "gk_browser_snapshot",
        "screenshot": "gk_browser_screenshot",
        "click": "gk_browser_click",
        "fill": "gk_browser_fill",
        "register_shot": "register_screenshot",
        "register_journey": "register_ui_journey",
    },
    "gk_mode": {
        "list": "list_modes",
        "protocol": "get_protocol",
        "constitution": "get_constitution",
        "activate": "activate_mode",
        "skill_catalog": "skill_catalog",
        "skills_loaded": "record_skills_loaded",
        "route": "godkiller_route_intent",
    },
    "gk_handoff": {
        "write_spec": "write_spec",
        "write_feedback": "write_feedback",
        "read": "read_handoff",
        "require_spec": "require_spec_gate",
    },
    "gk_meta": {
        "secret_keys": "godkiller_secret_keys",
        "plan_validate": "gk_plan_validate",
        "plan_template": "gk_plan_template",
    },
}

FACADE_DESC = {
    "gk_route": "Classify intent into /ask|/plan|/debug|/ultradeep|/verify.",
    "gk_task": "Task lifecycle: open, hypothesize, graph, policy, blast_radius, edit_safe, failing_slice.",
    "gk_phase": "Phase machine: assert, claim_done, rubric. Blocks illegal Antigravity phase skips.",
    "gk_evidence": "Evidence: submit, capture_shot, visual_critic, screenshot, journey, inspect_image.",
    "gk_verify": "Verification: bundle (pytest/cmds), soak, loop_*, competitor, compare, ladder.",
    "gk_memory": "Workflow memory graph: lessons, marathon, query_graph, what_blocked, upsert_episode.",
    "gk_code": "Code intel: map, search, find, preview, read_full/read_all, ast_grep, auto_fix, council.",
    "gk_scan": "Security scan (AST/CWE heuristics) and optional semgrep CLI.",
    "gk_browser": "Browser automation (Playwright when installed): navigate, snapshot, screenshot, click, fill.",
    "gk_mode": "Modes/protocols/skills/constitution for Antigravity.",
    "gk_handoff": "Spec/feedback handoff gates.",
    "gk_meta": "Secrets key listing + 9-step plan template/validate.",
}


def _tools() -> List[Any]:
    """Test helper: return facade names as lightweight objects."""

    class _T:
        def __init__(self, name: str):
            self.name = name

    return [_T(n) for n in FACADE_ACTIONS]


def _flatten_args(arguments: Dict[str, Any]) -> Dict[str, Any]:
    nested = arguments.get("args")
    flat = {k: v for k, v in arguments.items() if k not in ("action", "args")}
    if isinstance(nested, dict):
        return {**nested, **flat}
    return flat


async def _dispatch_facade(facade: str, action: str, args: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
    amap = FACADE_ACTIONS[facade]
    if action not in amap:
        return json.dumps({"error": f"unknown action {action}", "allowed": sorted(amap.keys())}, indent=2)
    payload = dict(args or {})
    payload.update({k: v for k, v in kwargs.items() if v is not None})
    # Also accept flat kwargs already merged
    if facade == "gk_mode" and action == "activate" and payload.get("goal"):
        decision = router.route_intent(str(payload.get("goal") or ""))
        payload.setdefault("kind", "bugfix" if decision.command == "/debug" else "feature")
    if facade == "gk_task" and action == "open" and payload.get("goal") and not payload.get("kind"):
        decision = router.route_intent(str(payload["goal"]))
        payload["kind"] = "bugfix" if decision.command == "/debug" else "feature"
    # Map prompt for route actions
    if amap[action] == "godkiller_route_intent" and "prompt" not in payload and "goal" in payload:
        payload["prompt"] = payload["goal"]
    result = await handle_tool(amap[action], payload)
    # handle_tool returns List[TextContent]
    if result and hasattr(result[0], "text"):
        return result[0].text
    return json.dumps(result, default=str)


def _register_facades() -> None:
    for facade_name, amap in FACADE_ACTIONS.items():
        actions = sorted(amap.keys())
        desc = FACADE_DESC[facade_name] + f" actions={actions}"

        def _make(fname: str):
            async def _tool(action: str, args: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
                return await _dispatch_facade(fname, action, args, **kwargs)

            _tool.__name__ = fname
            _tool.__doc__ = desc
            return _tool

        app.add_tool(_make(facade_name), name=facade_name, description=desc)


_register_facades()


def main() -> None:
    print("Starting GODKILLER MCP Server (facade surface)...", file=sys.stderr, flush=True)
    app.run_stdio_async()


if __name__ == "__main__":
    main()
