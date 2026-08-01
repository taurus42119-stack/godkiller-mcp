"""GODKILLER MCP Server — slim facade surface (~12 tools) over legacy dispatch."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP as _Server
except ImportError:  # pragma: no cover
    from mcp.server.mcpserver import MCPServer as _Server  # type: ignore

from godkiller_mcp.dispatch import handle_tool, router
from godkiller_mcp.compact_io import dumps_payload

app = _Server(
    name="GODKILLER",
    instructions=(
        "GODKILLER=MCP proof kernel (not Enterprise/OS). Compact payloads by default. "
        "gk_meta.status then read agents_md_path. Modes: gk_mode.activate (preview only; "
        "get_protocol if needed). Gates on disk beat chat. UI: visual_step sequence. "
        "plan_validate needs ### Phase N. detail/include_protocol/GODKILLER_VERBOSE=1 for fat dumps."
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
        "visual_step": "visual_step",
        "visual_sequence": "visual_sequence_status",
    },
    "gk_verify": {
        "bundle": "verify_bundle",
        "hollow": "hollow_surface",
        "probe": "fault_probe",
        "exit": "exit_checklist",
        "ledger": "ledger_tail",
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
        "council_submit": "godkiller_council_submit",
        "council_finalize": "godkiller_council_finalize",
        "skillify": "godkiller_auto_skillify",
        "read_full": "gk_code_read_full",
        "swarm_spawn": "swarm_spawn",
        "swarm_submit": "swarm_submit",
        "swarm_collect": "swarm_collect",
    },
    "gk_guard": {
        "write": "write_guard",
        "set_paths": "write_guard_set_paths",
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
        "ultradeep_queue": "ultradeep_queue_files",
        "ultradeep_think": "ultradeep_think_file",
        "ultradeep_plan": "ultradeep_plan_file",
        "ultradeep_advance": "ultradeep_advance_file",
        "ultradeep_status": "ultradeep_file_status",
        "ultradeep_refute": "ultradeep_plan_refute",
        "repair_wake": "ultradeep_repair_wake",
        "view_start": "view_start",
        "view_search": "view_record_search",
        "view_attack": "view_record_attack",
        "view_draft": "view_draft_plan",
        "view_refute": "view_refute_plan",
        "view_finalize": "view_finalize",
        "view_propose_study": "view_propose_study",
        "debug_ctf_start": "debug_self_ctf_start",
        "debug_ctf_tick": "debug_self_ctf_tick",
        "debug_ctf_run_until": "debug_self_ctf_run_until",
        "tool_propose": "tool_propose",
        "tool_approve": "tool_approve",
        "tool_reject": "tool_reject_all",
        "tool_used": "tool_used",
        "tool_status": "tool_propose_status",
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
        "status": "gk_honesty_status",
    },
}

FACADE_DESC = {
    "gk_route": "Classify intent into /ask|/plan|/debug|/ultradeep|/view|/verify.",
    "gk_task": "Task lifecycle: open, hypothesize, graph, policy, blast_radius, edit_safe, failing_slice.",
    "gk_phase": "Phase machine: assert, claim_done, rubric. Blocks illegal Antigravity phase skips.",
    "gk_evidence": "Evidence: submit, capture_shot, visual_critic, visual_step (~10-shot QA), visual_sequence, screenshot, journey, inspect_image.",
    "gk_verify": "Verification: bundle, exit (stage_board progress), soak, probe, loop_*, competitor, compare, ladder.",
    "gk_memory": "Workflow memory graph: lessons, marathon, query_graph, what_blocked, upsert_episode.",
    "gk_code": "Code intel helpers (map/search/read). council/swarm/pipeline/self_heal = best-effort, not magic fix or formal proof.",
    "gk_guard": "Write allowlist policy brain for host PreToolUse — only blocks native Write/Edit when the host actually wires the hook.",
    "gk_scan": "Best-effort regex CWE heuristics (signal, not a pro audit); optional semgrep CLI.",
    "gk_browser": "Browser automation (Playwright when installed): navigate, snapshot, screenshot, click, fill.",
    "gk_mode": "Modes/protocols/skills + ultradeep/view/debug + tool_propose (search≠install) + plan_refute wake.",
    "gk_handoff": "Spec/feedback handoff gates.",
    "gk_meta": "Honesty status (disk MCP configs + real facades) + secrets key listing + 9-step plan template/validate.",
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
        return dumps_payload({"error": f"unknown action {action}", "allowed": sorted(amap.keys())})
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
        n = len(amap)
        desc = (
            f"{FACADE_DESC[facade_name]} Pass action= and args={{}}. "
            f"{n} actions; unknown action returns allowed list (saves schema tokens)."
        )

        def _make(fname: str, description: str):
            async def _tool(action: str, args: Optional[Dict[str, Any]] = None, **kwargs: Any) -> str:
                return await _dispatch_facade(fname, action, args, **kwargs)

            _tool.__name__ = fname
            _tool.__doc__ = description
            return _tool

        app.add_tool(_make(facade_name, desc), name=facade_name, description=desc)


_register_facades()


def main() -> None:
    import os

    from godkiller_mcp.ship_mode import profile, relax_enabled

    print("Starting GODKILLER MCP Server (facade surface)...", file=sys.stderr, flush=True)
    if relax_enabled():
        print(
            "WARNING: GODKILLER_DEV_RELAX active — armor gates soft/disarmed "
            "(local experiments only; not ship posture).",
            file=sys.stderr,
            flush=True,
        )
    elif profile() == "ship" and os.environ.get("GODKILLER_DEV_RELAX", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        print(
            "NOTE: GODKILLER_DEV_RELAX ignored under PROFILE=ship — armor stays armed.",
            file=sys.stderr,
            flush=True,
        )
    # FastMCP.run() is sync and awaits run_stdio_async via anyio.
    # Calling run_stdio_async() bare exits immediately → host "MCP Error"/EOF.
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
