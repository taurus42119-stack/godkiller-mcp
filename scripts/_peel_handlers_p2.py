"""Extract dispatch if-blocks into handlers/{task,edit_safe,verify}.py and strip from dispatch."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "godkiller_mcp" / "dispatch.py"
HANDLERS = ROOT / "src" / "godkiller_mcp" / "handlers"

GROUPS: dict[str, list[str]] = {
    "task": [
        "open_task",
        "propose_hypothesis",
        "assert_phase",
        "submit_evidence",
        "evaluate_rubric",
        "request_claim_done",
        "policy_decide",
        "get_task_graph",
    ],
    "edit_safe": ["get_failing_slice", "blast_radius", "check_edit_safe"],
    "verify": [
        "verify_bundle",
        "hollow_surface",
        "exit_checklist",
        "ledger_tail",
        "fault_probe",
    ],
    "code_intel_tools": [
        "godkiller_exhaustive_read",
        "godkiller_auto_skillify",
        "godkiller_council_debate",
        "godkiller_council_submit",
        "godkiller_council_finalize",
        "godkiller_pipeline",
        "godkiller_self_heal",
        "godkiller_confidence_check",
        "godkiller_deep_scrape",
        "godkiller_log_trace",
        "godkiller_auto_fix",
        "godkiller_ast_grep",
        "godkiller_security_scan",
        "godkiller_repo_map",
        "godkiller_hyper_search",
        "godkiller_fast_find",
        "godkiller_context_preview",
    ],
    "modes_ultradeep": [
        "list_modes",
        "get_protocol",
        "get_constitution",
        "skill_catalog",
        "record_skills_loaded",
        "activate_mode",
        "ultradeep_queue_files",
        "ultradeep_think_file",
        "ultradeep_plan_file",
        "ultradeep_advance_file",
        "ultradeep_file_status",
        "ultradeep_plan_refute",
        "ultradeep_repair_wake",
    ],
    "visual_marathon": [
        "capture_shot",
        "visual_critic",
        "soak_run",
        "competitor_scan",
        "compare_delta",
        "set_ambition_ladder",
        "retrieve_lessons_verified",
        "register_screenshot",
        "visual_step",
        "visual_sequence_status",
        "register_ui_journey",
        "ingest_lesson",
        "retrieve_lessons",
        "marathon_init",
        "marathon_load_progress",
        "marathon_save_progress",
        "marathon_search_gate",
        "marathon_next_wake",
        "marathon_list",
    ],
}


HEADER = '''"""Domain handlers peeled from dispatch (facade names unchanged)."""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.types import TextContent


async def handle(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    import asyncio
    from pathlib import Path

    from godkiller_mcp.code_intel import (
        AutoFixEngine,
        AutoSkillifyEngine,
        AstGrepEngine,
        ContextPreviewEngine,
        CouncilDebateEngine,
        DeepScrapeEngine,
        EpistemicConfidenceGate,
        ExhaustiveReaderEngine,
        FastFindEngine,
        HyperSearchEngine,
        LogTraceEngine,
        PipelineRunner,
        RepoMapGenerator,
        SecurityScanEngine,
        SelfHealingEngine,
        blast_radius,
        check_edit_safe,
        get_failing_slice,
        require_blast_before_edit,
    )
    from godkiller_mcp.dispatch import (
        STORE_DIR,
        STATE_ROOT,
        _json,
        browser,
        handoff,
        lessons,
        loops,
        marathon,
        modes,
        plan_os,
        policy,
        store,
        verify_runner,
        vision,
        workflow,
        pw_browser,
    )
    from godkiller_mcp import ultradeep_engine as ude
    from godkiller_mcp.policy import rubric_for_kind
    from godkiller_mcp.quality_gates import (
        LADDER_LEVELS,
        build_compare_delta,
        build_competitor_scan,
        next_ladder_level,
        run_soak,
        run_visual_critic,
    )
    from godkiller_mcp.schema import EvidenceType, Phase, PolicyAction, TaskKind
    from godkiller_mcp.skill_catalog import (
        build_catalog,
        filter_catalog,
        suggest_from_catalog,
    )

    arguments = arguments or {}
__BODY__
    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in __NAMES__:
        reg(tool, _entry)
'''


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(True)
    starts: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r'^    if name == ["\']([^"\']+)["\']:\s*$', line)
        if m:
            starts.append((i, m.group(1)))

    def block(name: str) -> tuple[int, int, str]:
        idx = next(i for i, n in starts if n == name)
        end = next((j for j, _ in starts if j > idx), len(lines))
        return idx, end, "".join(lines[idx:end])

    remove_ranges: list[tuple[int, int]] = []
    for group, names in GROUPS.items():
        bodies: list[str] = []
        kept: list[str] = []
        for n in names:
            try:
                a, b, body = block(n)
            except StopIteration:
                print("skip missing", n)
                continue
            remove_ranges.append((a, b))
            bodies.append(body)
            kept.append(n)
        if not kept:
            print("skip empty group", group)
            continue
        text = HEADER.replace("__BODY__", "".join(bodies)).replace(
            "__NAMES__", repr(kept)
        )
        (HANDLERS / f"{group}.py").write_text(text, encoding="utf-8")
        print("wrote", group, "tools", kept)

    remove_ranges.sort(reverse=True)
    for a, b in remove_ranges:
        del lines[a:b]

    SRC.write_text("".join(lines), encoding="utf-8")
    print("dispatch.py stripped; remaining LOC", len(lines))


if __name__ == "__main__":
    main()
