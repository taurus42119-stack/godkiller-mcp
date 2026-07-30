"""Legacy tool dispatch (internal). Facades in server.py call handle_tool()."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from mcp.types import TextContent

from godkiller_mcp.browser_bridge import BrowserEvidenceBridge, JourneyResult, JourneyStep
from godkiller_mcp.code_intel import (
    blast_radius,
    check_edit_safe,
    get_failing_slice,
    require_blast_before_edit,
    RepoMapGenerator,
    HyperSearchEngine,
    FastFindEngine,
    ContextPreviewEngine,
    AstGrepEngine,
    SecurityScanEngine,
    DeepScrapeEngine,
    LogTraceEngine,
    AutoFixEngine,
    PipelineRunner,
    SelfHealingEngine,
    EpistemicConfidenceGate,
    ExhaustiveReaderEngine,
    AutoSkillifyEngine,
    CouncilDebateEngine,
)
from godkiller_mcp.epistemic_router import EpistemicRouter
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.handoff_docs import SpecFeedbackStore
from godkiller_mcp.loop_guard import LoopDetector
from godkiller_mcp.marathon import MarathonRelay
from godkiller_mcp.memory_lessons import LessonMemory, MemoryTier
from godkiller_mcp.modes import MODES, ModeProtocolStore
from godkiller_mcp.skill_catalog import build_catalog, filter_catalog, suggest_from_catalog
from godkiller_mcp.policy import PolicyEngine, rubric_for_kind
from godkiller_mcp.schema import EvidenceType, Phase, PolicyAction, TaskKind
from godkiller_mcp.secrets_loader import ScopeSafeSecretsLoader
from godkiller_mcp.quality_gates import (
    LADDER_LEVELS,
    build_compare_delta,
    build_competitor_scan,
    next_ladder_level,
    run_soak,
    run_visual_critic,
)
from godkiller_mcp.verify_bundle import VerifyBundleRunner
from godkiller_mcp.vision_bridge import VisionBridge
from godkiller_mcp.plan_os import PlanOS
from godkiller_mcp.workflow_graph import WorkflowGraph
from godkiller_mcp.browser_runtime import PlaywrightBrowser
from godkiller_mcp.scan_runtime import run_semgrep

ROOT = Path(__file__).resolve().parents[2]
STORE_DIR = ROOT / "arena" / "results" / "tasks"
STORE_DIR.mkdir(parents=True, exist_ok=True)
MARATHON_DIR = ROOT / "arena" / "results" / "marathon"
MARATHON_DIR.mkdir(parents=True, exist_ok=True)
HANDOFF_DIR = ROOT / "arena" / "results" / "handoff"
HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

store = EvidenceStore(persist_dir=STORE_DIR)
policy = PolicyEngine()
browser = BrowserEvidenceBridge(store, artifact_dir=ROOT / "arena" / "results" / "ui_artifacts")
lessons = LessonMemory(str(ROOT / "lessons.db"))
marathon = MarathonRelay(MARATHON_DIR)
modes = ModeProtocolStore(ROOT / ".agents")
verify_runner = VerifyBundleRunner()
loops = LoopDetector()
handoff = SpecFeedbackStore(HANDOFF_DIR)
secrets = ScopeSafeSecretsLoader(ROOT / ".env")
router = EpistemicRouter()
vision = VisionBridge()
plan_os = PlanOS()
workflow = WorkflowGraph(store)
pw_browser = PlaywrightBrowser(artifact_dir=ROOT / "arena" / "results" / "ui_artifacts")


def _json(data: Any) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


async def handle_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    if name == "godkiller_route_intent":
        decision = router.route_intent(arguments["prompt"])
        return _json(decision.__dict__)

    if name == "godkiller_inspect_image":
        result = vision.analyze_screenshot(arguments["path"])
        return _json(result.__dict__)

    if name == "godkiller_secret_keys":
        return _json(
            {
                "env_path": str(secrets.env_path),
                "keys": sorted(secrets.get_all_secrets().keys()),
                "note": "Secret values are never returned by this tool.",
            }
        )

    if name == "godkiller_exhaustive_read":
        dpath = arguments["dir_path"]
        mfiles = arguments.get("max_files", 200)
        engine = ExhaustiveReaderEngine()
        res = engine.read_all(dpath, max_files=mfiles)
        return _json(res)

    if name == "godkiller_auto_skillify":
        sname = arguments["skill_name"]
        sdesc = arguments["description"]
        sinst = arguments["instructions"]
        wroot = arguments.get("workspace_root", ".")
        engine = AutoSkillifyEngine()
        res = engine.skillify(sname, sdesc, sinst, workspace_root=wroot)
        return _json(res)

    if name == "godkiller_council_debate":
        prop = arguments["proposed_code_or_plan"]
        ctx = arguments.get("context", {})
        engine = CouncilDebateEngine()
        res = engine.debate(prop, context=ctx)
        return _json(res)

    if name == "godkiller_pipeline":
        steps_arg = arguments["steps"]
        engine = PipelineRunner()
        res = engine.run_pipeline(steps_arg)
        return _json(res)

    if name == "godkiller_self_heal":
        ftool = arguments["failed_tool"]
        eout = arguments["error_or_output"]
        tctx = arguments.get("task_context", {})
        engine = SelfHealingEngine()
        res = engine.heal(ftool, eout, task_context=tctx)
        return _json(res)

    if name == "godkiller_confidence_check":
        fpath = arguments["file_path"]
        ksyms = arguments.get("known_symbols", [])
        hsearched = arguments.get("has_searched", False)
        engine = EpistemicConfidenceGate()
        res = engine.evaluate(fpath, known_symbols=ksyms, has_searched=hsearched)
        return _json(res)

    if name == "godkiller_deep_scrape":
        u_or_h = arguments["url_or_html"]
        mlength = arguments.get("max_length", 5000)
        engine = DeepScrapeEngine()
        res = engine.scrape(u_or_h, max_length=mlength)
        return _json(res)

    if name == "godkiller_log_trace":
        lout = arguments["log_output"]
        engine = LogTraceEngine()
        res = engine.parse_log(lout)
        return _json(res)

    if name == "godkiller_auto_fix":
        fpath = arguments["file_path"]
        pat = arguments["pattern"]
        repl = arguments["replacement"]
        prev_only = arguments.get("preview_only", True)
        engine = AutoFixEngine()
        res = engine.fix(fpath, pattern=pat, replacement=repl, preview_only=prev_only)
        return _json(res)

    if name == "godkiller_ast_grep":
        pat = arguments["pattern"]
        spath = arguments.get("search_path", ".")
        lang = arguments.get("lang", "python")
        mresults = arguments.get("max_results", 50)
        engine = AstGrepEngine()
        res = engine.search(pat, search_path=spath if spath != "." else ROOT, lang=lang, max_results=mresults)
        return _json(res)

    if name == "godkiller_security_scan":
        tpath = arguments.get("target_path", ".")
        sthreshold = arguments.get("severity_threshold", "medium")
        engine = SecurityScanEngine()
        res = engine.scan(target_path=tpath if tpath != "." else ROOT, severity_threshold=sthreshold)
        return _json(res)

    if name == "godkiller_repo_map":
        wroot = arguments.get("workspace_root", ".")
        mtokens = arguments.get("max_tokens", 1000)
        generator = RepoMapGenerator(wroot if wroot != "." else ROOT)
        map_text = generator.get_repo_map(max_tokens=mtokens)
        return [TextContent(type="text", text=map_text)]

    if name == "godkiller_hyper_search":
        pat = arguments["pattern"]
        spath = arguments.get("search_path", ".")
        mresults = arguments.get("max_results", 100)
        searcher = HyperSearchEngine()
        res = searcher.search(pat, search_path=spath if spath != "." else ROOT, max_results=mresults)
        return _json(res)

    if name == "godkiller_fast_find":
        npat = arguments["name_pattern"]
        spath = arguments.get("search_path", ".")
        mresults = arguments.get("max_results", 100)
        finder = FastFindEngine()
        res = finder.find(npat, search_path=spath if spath != "." else ROOT, max_results=mresults)
        return _json(res)

    if name == "godkiller_context_preview":
        fpath = arguments["file_path"]
        sline = arguments.get("start_line", 1)
        eline = arguments.get("end_line", 100)
        previewer = ContextPreviewEngine()
        res = previewer.preview(fpath, start_line=sline, end_line=eline)
        return _json(res)

    if name == "open_task":
        state = store.open_task(
            kind=arguments["kind"],
            goal=arguments["goal"],
            project_id=arguments.get("project_id", "default"),
        )
        rubric = [
            {"id": r.id, "description": r.description}
            for r in rubric_for_kind(state.handle.kind)
        ]
        return _json(
            {
                "task_id": state.handle.task_id,
                "kind": state.handle.kind.value,
                "phase": state.handle.phase.value,
                "rubric_id": state.handle.rubric_id,
                "rubric": rubric,
                "goal": state.handle.goal,
            }
        )

    if name == "propose_hypothesis":
        from godkiller_mcp.search_gates import assert_phase_search_gate

        hyp = store.propose_hypothesis(
            task_id=arguments["task_id"],
            claim=arguments["claim"],
            support_refs=arguments.get("support_refs"),
            refute_refs=arguments.get("refute_refs"),
        )
        try:
            cur = store.get(arguments["task_id"])
            ok_s, reason_s = assert_phase_search_gate(cur, Phase.HYPOTHESIZE)
            if ok_s:
                store.assert_phase(arguments["task_id"], Phase.HYPOTHESIZE)
            # If search missing, still keep hypothesis but do not advance phase via MCP shortcut
            _ = reason_s
        except ValueError:
            pass
        return _json(hyp.model_dump())

    if name == "assert_phase":
        from godkiller_mcp.search_gates import assert_phase_search_gate
        from godkiller_mcp.skill_gates import assert_phase_skill_gate

        cur = store.get(arguments["task_id"])
        ok_s, reason_s = assert_phase_search_gate(cur, arguments["phase"])
        if not ok_s:
            return _json(
                {
                    "allowed": False,
                    "reason": reason_s,
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
        ok_sk, reason_sk = assert_phase_skill_gate(cur, arguments["phase"])
        if not ok_sk:
            return _json(
                {
                    "allowed": False,
                    "reason": reason_sk,
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
        state = store.assert_phase(arguments["task_id"], arguments["phase"])
        loops.note_phase_advance(arguments["task_id"], arguments["phase"])
        loops.record(
            arguments["task_id"],
            "assert_phase",
            signature=f"assert_phase:{arguments['phase']}",
            phase=arguments["phase"],
        )
        return _json(
            {
                "allowed": True,
                "task_id": state.handle.task_id,
                "phase": state.handle.phase.value,
            }
        )

    if name == "submit_evidence":
        from godkiller_mcp.search_gates import normalize_web_search_payload

        payload = arguments.get("payload") or {}
        if isinstance(payload, dict):
            payload = normalize_web_search_payload(payload)
        ev = store.submit_evidence(
            task_id=arguments["task_id"],
            evidence_type=arguments["type"],
            summary=arguments["summary"],
            payload=payload,
            uri=arguments.get("uri"),
            contradicts=arguments.get("contradicts"),
        )
        # Mirror queries into task metadata for durable gate checks
        queries = (payload or {}).get("queries") if isinstance(payload, dict) else None
        if queries:
            existing = list((store.get(arguments["task_id"]).handle.metadata or {}).get("search_queries") or [])
            merged = list(dict.fromkeys([*existing, *[str(q) for q in queries if str(q).strip()]]))
            store.update_metadata(arguments["task_id"], {"search_queries": merged})
        return _json(ev.model_dump())

    if name == "evaluate_rubric":
        state = store.get(arguments["task_id"])
        results = policy.evaluate_rubric(state)
        return _json(
            {
                "task_id": state.handle.task_id,
                "all_passed": policy.all_passed(results),
                "results": [r.model_dump() for r in results],
            }
        )

    if name == "request_claim_done":
        state = store.get(arguments["task_id"])
        loops.record(
            arguments["task_id"],
            "request_claim_done",
            signature="request_claim_done",
            phase=state.handle.phase,
        )
        # Feature UI gate
        if state.handle.kind == TaskKind.FEATURE:
            ok_ui, reason_ui = browser.require_ui_proof_for_feature(state.handle.task_id)
            if not ok_ui:
                blocked = workflow.what_blocked_claim_done(state.handle.task_id, reason_ui)
                return _json({"allowed": False, "reason": reason_ui, "action": PolicyAction.BLOCK.value, "graph": blocked})
        handoff_ok = None
        handoff_reason = ""
        if arguments.get("handoff_slug"):
            handoff_ok, handoff_reason = handoff.require_passing_feedback(arguments["handoff_slug"])
        allowed, results, reason = policy.request_claim_done(
            state,
            require_verify_bundle=arguments.get("require_verify_bundle", True),
            handoff_feedback_ok=handoff_ok,
            handoff_reason=handoff_reason,
            require_quality_loop=arguments.get("require_quality_loop", True),
            require_competitor_loop=arguments.get("require_competitor_loop", True),
            min_ambition_ladder=arguments.get("min_ambition_ladder") or "L1_presence",
        )
        if allowed:
            try:
                store.assert_phase(state.handle.task_id, Phase.CLAIM_DONE)
                loops.note_phase_advance(state.handle.task_id, Phase.CLAIM_DONE)
            except ValueError:
                state.handle.phase = Phase.CLAIM_DONE
            store.mark_closed(state.handle.task_id)
            state.last_policy_action = PolicyAction.ALLOW_CLAIM_DONE
        else:
            state.last_policy_action = PolicyAction.BLOCK
            state.failure_streak += 1
        out = {
            "allowed": allowed,
            "reason": reason,
            "action": state.last_policy_action.value if state.last_policy_action else None,
            "results": [r.model_dump() for r in results],
        }
        if not allowed:
            out["graph"] = workflow.what_blocked_claim_done(state.handle.task_id, reason)
        return _json(out)

    if name == "policy_decide":
        state = store.get(arguments["task_id"])
        action = policy.decide(state)
        state.last_policy_action = action
        return _json({"task_id": state.handle.task_id, "action": action.value, "phase": state.handle.phase.value})

    if name == "get_task_graph":
        return _json(store.dump_graph(arguments["task_id"]))

    if name == "get_failing_slice":
        report = get_failing_slice(arguments["test_output"], arguments.get("workspace"))
        out: Dict[str, Any] = report.to_evidence_payload()
        if arguments.get("attach", True) and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.FAILING_SLICE,
                summary=report.summary,
                payload=report.to_evidence_payload(),
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError:
                pass
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "blast_radius":
        report = blast_radius(arguments["symbol"], arguments["workspace"])
        out = report.to_evidence_payload()
        if arguments.get("attach", True) and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.BLAST_RADIUS,
                summary=report.summary,
                payload=report.to_evidence_payload(),
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError:
                pass
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "check_edit_safe":
        task_id = arguments.get("task_id")
        if task_id:
            state = store.get(task_id)
            require_plan = arguments.get("require_plan")
            if require_plan is None:
                require_plan = state.handle.phase.value in ("fix", "verify", "claim_done")
            if require_plan:
                plan_meta = (state.handle.metadata or {}).get("plan_validation")
                if not plan_meta or not plan_meta.get("valid"):
                    plan_dict = (state.handle.metadata or {}).get("plan_dict")
                    if plan_dict:
                        plan_meta = plan_os.validate(plan_dict)
                        store.update_metadata(task_id, {"plan_validation": plan_meta})
                    if not plan_meta or not plan_meta.get("valid"):
                        return _json(
                            {
                                "allowed": False,
                                "safe": False,
                                "reason": "9-step plan missing/incomplete — call gk_meta action=plan_validate first",
                                "action": PolicyAction.BLOCK.value,
                            }
                        )
        if task_id and arguments.get("require_blast", True):
            state = store.get(task_id)
            ok_b, reason_b = require_blast_before_edit(state.evidence_types())
            if not ok_b:
                loops.record(task_id, "check_edit_safe", signature="edit_blocked_no_blast", phase=state.handle.phase)
                return _json(
                    {
                        "allowed": False,
                        "safe": False,
                        "reason": reason_b,
                        "action": PolicyAction.BLOCK.value,
                    }
                )
        report = check_edit_safe(arguments["paths"], arguments["workspace"])
        out = report.to_evidence_payload()
        out["allowed"] = True
        if arguments.get("attach", True) and task_id:
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.EDIT_SAFE,
                summary=report.summary,
                payload=report.to_evidence_payload(),
            )
            out["evidence_id"] = ev.id
            loops.record(task_id, "check_edit_safe", signature="check_edit_safe:" + ",".join(arguments["paths"][:3]))
        return _json(out)

    if name == "verify_bundle":
        result = verify_runner.run(
            arguments["workspace"],
            arguments.get("commands"),
        )
        out = result.to_payload()
        task_id = arguments.get("task_id")
        if arguments.get("attach", True) and task_id:
            ev_type = EvidenceType.PASSING_TEST if result.passed else EvidenceType.EXIT_CODE
            if result.hack_blocked:
                ev_type = EvidenceType.EXIT_CODE
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=ev_type,
                summary=result.summary,
                payload=result.to_payload(),
            )
            # Always also record exit_code evidence for rubric EXIT_CODE checks
            if result.passed:
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.EXIT_CODE,
                    summary="verify_bundle exit 0",
                    payload=result.to_payload(),
                )
                try:
                    store.assert_phase(task_id, Phase.VERIFY)
                    loops.note_phase_advance(task_id, Phase.VERIFY)
                except ValueError:
                    pass
            out["evidence_id"] = ev.id
            loops.record(
                task_id,
                "verify_bundle",
                signature=f"verify_bundle:{'pass' if result.passed else 'fail'}",
                phase=store.get(task_id).handle.phase,
            )
        return _json(out)

    if name == "record_tool_event":
        phase = arguments.get("phase")
        if not phase and arguments.get("task_id"):
            try:
                phase = store.get(arguments["task_id"]).handle.phase
            except Exception:
                phase = None
        verdict = loops.record(
            arguments["task_id"],
            arguments["tool"],
            signature=arguments.get("signature") or arguments["tool"],
            phase=phase,
        )
        return _json(verdict.to_dict())

    if name == "loop_status":
        return _json(loops.status(arguments["task_id"]))

    if name == "write_spec":
        from godkiller_mcp.search_gates import write_spec_search_gate

        require_search = arguments.get("require_search", True)
        kind = arguments.get("kind") or "feature"
        queries = list(arguments.get("search_queries") or [])
        marathon_q: list = []
        slug = arguments["slug"]
        try:
            marathon_q = list(marathon.load(slug).search_queries)
        except FileNotFoundError:
            marathon_q = handoff.read_search_queries(slug)
        if require_search:
            ok, reason, merged = write_spec_search_gate(
                queries,
                kind=kind,
                min_queries=arguments.get("min_queries"),
                marathon_queries=marathon_q,
            )
            if not ok:
                return _json({"allowed": False, "reason": reason, "action": PolicyAction.BLOCK.value})
        else:
            merged = list(dict.fromkeys([*queries, *marathon_q]))
        meta = handoff.write_spec(
            slug,
            arguments["content"],
            goal=arguments.get("goal") or "",
            search_queries=merged,
        )
        # Keep marathon in sync when present
        if merged:
            try:
                marathon.save(slug, search_queries=merged, last_handoff="write_spec recorded searches", bump_session=False)
            except FileNotFoundError:
                pass
        meta["allowed"] = True
        meta["search_count"] = len(merged)
        return _json(meta)

    if name == "write_feedback":
        meta = handoff.write_feedback(
            arguments["slug"],
            arguments["content"],
            score=float(arguments.get("score") or 0),
            passed=bool(arguments.get("passed")),
        )
        return _json(meta)

    if name == "read_handoff":
        return _json(handoff.read_pack(arguments["slug"]))

    if name == "require_spec_gate":
        ok, reason = handoff.require_spec(arguments["slug"])
        return _json({"allowed": ok, "reason": reason})

    if name == "capture_shot":
        path = arguments["path"]
        summary = arguments.get("summary") or "capture_shot evidence"
        p = Path(path)
        vision_result = vision.analyze_screenshot(p)
        payload = {
            "source": "capture_shot",
            "exists": p.exists(),
            "path": str(p.resolve()) if p.exists() else path,
            "size": p.stat().st_size if p.exists() else 0,
            "vision": vision_result.__dict__,
        }
        ev = store.submit_evidence(
            task_id=arguments["task_id"],
            evidence_type=EvidenceType.SCREENSHOT,
            summary=(
                summary
                if vision_result.passed
                else f"{summary} (VISION FAIL: {vision_result.description})"
            ),
            payload=payload,
            uri=str(p.resolve()) if p.exists() else path,
        )
        loops.record(arguments["task_id"], "capture_shot", signature=f"capture:{path}")
        return _json(ev.model_dump())

    if name == "visual_critic":
        state = store.get(arguments["task_id"])
        kind = arguments.get("kind") or state.handle.kind.value
        result = run_visual_critic(
            kind=kind,
            description=arguments["description"],
            checklist=arguments.get("checklist"),
            agent_verdict=arguments.get("agent_verdict"),
            findings=arguments.get("findings"),
        )
        out = result.to_payload()
        if arguments.get("attach", True):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.OTHER if result.verdict.value != "GREEN" else EvidenceType.LOG,
                summary=result.summary,
                payload=result.to_payload(),
            )
            out["evidence_id"] = ev.id
        if result.escalate:
            out["action"] = PolicyAction.ESCALATE_FRONTIER.value
            out["instruction"] = (
                "visual_critic RED: placeholders are failures not milestones. "
                "Fix visuals or escalate frontier, then re-run visual_critic."
            )
        loops.record(
            arguments["task_id"],
            "visual_critic",
            signature=f"visual_critic:{result.verdict.value}",
            phase=state.handle.phase,
        )
        return _json(out)

    if name == "soak_run":
        result = run_soak(
            duration_sec=float(arguments.get("duration_sec") or 30),
            errors=int(arguments.get("errors") or 0),
            stuck_pct=float(arguments.get("stuck_pct") or 0),
            notes=arguments.get("notes") or "",
            command=arguments.get("command"),
            workspace=arguments.get("workspace"),
        )
        out = result.to_payload()
        if arguments.get("attach", True):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.LOG if result.passed else EvidenceType.EXIT_CODE,
                summary=f"soak_run {'PASS' if result.passed else 'FAIL'}",
                payload=result.to_payload(),
            )
            out["evidence_id"] = ev.id
        loops.record(
            arguments["task_id"],
            "soak_run",
            signature=f"soak:{'pass' if result.passed else 'fail'}",
        )
        return _json(out)

    if name == "competitor_scan":
        result = build_competitor_scan(
            arguments.get("queries") or [],
            arguments.get("competitors") or [],
            min_required=int(arguments.get("min_required") or 2),
        )
        out = result.to_payload()
        if arguments.get("attach", True):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.OTHER,
                summary=f"competitor_scan n={len(result.competitors)}",
                payload=result.to_payload(),
            )
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "compare_delta":
        result = build_compare_delta(
            arguments.get("axes") or {},
            still_losing=arguments.get("still_losing"),
            notes=arguments.get("notes") or "",
            best_competitor=arguments.get("best_competitor") or "",
        )
        out = result.to_payload()
        if arguments.get("attach", True):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.OTHER,
                summary=(
                    "compare_delta PASS"
                    if result.passed
                    else "compare_delta still losing — continue ladder"
                ),
                payload=result.to_payload(),
            )
            out["evidence_id"] = ev.id
        if result.still_losing:
            out["action"] = PolicyAction.REPLAN.value
            out["instruction"] = (
                "Still losing vs competitors. Advance ambition ladder / improve; do not claim."
            )
        return _json(out)

    if name == "set_ambition_ladder":
        state = store.get(arguments["task_id"])
        current = (state.handle.metadata or {}).get("ambition_ladder") or "L0_core"
        if arguments.get("advance"):
            level = next_ladder_level(current)
        else:
            level = arguments.get("level") or current
        if level not in LADDER_LEVELS:
            raise ValueError(f"Invalid ladder level: {level}")
        store.update_metadata(arguments["task_id"], {"ambition_ladder": level})
        return _json(
            {
                "task_id": arguments["task_id"],
                "previous": current,
                "ambition_ladder": level,
                "next_suggested": next_ladder_level(level),
            }
        )

    if name == "retrieve_lessons_verified":
        payload = lessons.retrieve_verified(
            project_id=arguments["project_id"],
            query=arguments["query"],
            limit=int(arguments.get("limit") or 5),
            tier=arguments.get("tier"),
        )
        if arguments.get("attach") and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.LESSON,
                summary=f"Verified lessons injected: {payload['count_injected']}",
                payload=payload,
            )
            payload["evidence_id"] = ev.id
        return _json(payload)

    if name == "register_screenshot":
        ev = browser.register_screenshot(
            arguments["task_id"],
            arguments["path"],
            arguments.get("summary", "UI screenshot evidence"),
        )
        return _json(ev.model_dump())

    if name == "register_ui_journey":
        steps = [
            JourneyStep(
                action=s.get("action", ""),
                target=s.get("target", ""),
                expect=s.get("expect", ""),
                screenshot_uri=s.get("screenshot_uri"),
            )
            for s in arguments.get("steps") or []
        ]
        journey = JourneyResult(
            name=arguments["name"],
            passed=bool(arguments["passed"]),
            steps=steps,
            screenshot_uris=arguments.get("screenshot_uris") or [],
            notes=arguments.get("notes") or "",
        )
        ev = browser.register_journey(arguments["task_id"], journey)
        return _json(ev.model_dump())

    if name == "ingest_lesson":
        lesson = lessons.ingest_lesson(
            project_id=arguments["project_id"],
            task_id=arguments["task_id"],
            content=arguments["content"],
            tags=arguments.get("tags"),
            evidence_ids=arguments.get("evidence_ids"),
            task_passed=bool(arguments["task_passed"]),
            tier=arguments.get("tier") or MemoryTier.SEMANTIC,
        )
        if lesson is None:
            return _json({"stored": False, "reason": "Rejected: task_passed must be true."})
        return _json({"stored": True, "lesson": lesson.__dict__})

    if name == "retrieve_lessons":
        found = lessons.retrieve(
            project_id=arguments["project_id"],
            query=arguments["query"],
            limit=int(arguments.get("limit") or 5),
        )
        payload = lessons.export_evidence_payload(found)
        if arguments.get("attach") and arguments.get("task_id"):
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.LESSON,
                summary=f"Retrieved {len(found)} lessons",
                payload=payload,
            )
            payload["evidence_id"] = ev.id
        return _json(payload)

    if name == "marathon_init":
        state = marathon.init(
            slug=arguments["slug"],
            goal=arguments["goal"],
            kind=arguments.get("kind") or "feature",
            plan_path=arguments.get("plan_path"),
            task_id=arguments.get("task_id"),
        )
        # Also open kernel task if none provided
        if not arguments.get("task_id"):
            opened = store.open_task(state.kind, state.goal, project_id="marathon")
            state = marathon.save(
                state.slug,
                task_id=opened.handle.task_id,
                last_handoff=state.last_handoff,
                bump_session=False,
            )
        return _json(
            {
                "state": json.loads(state.model_dump_json()),
                "progress_path": str(marathon.progress_path(state.slug)),
                "next_wake": marathon.next_wake_prompt(state.slug),
            }
        )

    if name == "marathon_load_progress":
        state = marathon.load(arguments["slug"])
        progress = marathon.progress_path(state.slug).read_text(encoding="utf-8")
        return _json(
            {
                "state": json.loads(state.model_dump_json()),
                "progress_md": progress,
                "next_wake": marathon.next_wake_prompt(state.slug),
            }
        )

    if name == "marathon_save_progress":
        state = marathon.save(
            arguments["slug"],
            task_id=arguments.get("task_id"),
            kernel_phase=arguments.get("kernel_phase"),
            current_plan_phase=arguments.get("current_plan_phase"),
            evidence_ids=arguments.get("evidence_ids"),
            search_queries=arguments.get("search_queries"),
            blockers=arguments.get("blockers"),
            failure_streak=arguments.get("failure_streak"),
            last_handoff=arguments["last_handoff"],
            closed=arguments.get("closed"),
            bump_session=arguments.get("bump_session", True),
        )
        return _json(
            {
                "state": json.loads(state.model_dump_json()),
                "next_wake": marathon.next_wake_prompt(state.slug),
                "progress_path": str(marathon.progress_path(state.slug)),
            }
        )

    if name == "marathon_search_gate":
        kwargs = {"slug": arguments["slug"]}
        if arguments.get("min_queries") is not None:
            kwargs["min_queries"] = int(arguments["min_queries"])
        ok, reason = marathon.require_search_gate(**kwargs)
        return _json({"allowed": ok, "reason": reason})

    if name == "marathon_next_wake":
        return _json(
            {
                "slug": arguments["slug"],
                "prompt": marathon.next_wake_prompt(arguments["slug"]),
            }
        )

    if name == "marathon_list":
        return _json({"slugs": marathon.list_slugs()})

    if name == "list_modes":
        return _json({"modes": modes.list_modes()})

    if name == "get_protocol":
        text = modes.get_protocol(arguments["mode"])
        return _json({"mode": arguments["mode"], "protocol_markdown": text})

    if name == "get_constitution":
        return _json({"constitution_markdown": modes.get_constitution()})

    if name == "skill_catalog":
        from godkiller_mcp.skill_gates import build_catalog_evidence_payload

        skills_root = ROOT / ".agents" / "skills"
        entries = build_catalog(skills_root)
        query = arguments.get("query") or arguments.get("goal") or ""
        limit = int(arguments.get("limit") or 20)
        hits = filter_catalog(entries, query, limit=limit)
        shortlist_paths: List[str] = []
        out: Dict[str, Any] = {
            "total_indexed": len(entries),
            "returned": len(hits),
            "query": query,
            "skills": hits,
            "rule": (
                "Catalog is thin (no bodies). view_file at most 2–4 SKILL.md paths you pick, "
                "then record_skills_loaded. FORBIDDEN: skip because you feel confident."
            ),
        }
        goal = arguments.get("goal") or query
        if goal:
            from godkiller_mcp.modes import suggest_skills_for_goal

            forced = suggest_skills_for_goal(goal).get("must_view_file") or []
            pack = suggest_from_catalog(entries, goal, limit=4, forced_paths=forced)
            out["shortlist"] = pack
            shortlist_paths = pack.get("shortlist_paths") or []
        task_id = arguments.get("task_id")
        if task_id:
            payload = build_catalog_evidence_payload(
                query or goal,
                shortlist_paths=shortlist_paths,
                returned=len(hits),
            )
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"skill_catalog query={query or goal!r} n={len(hits)}",
                payload=payload,
            )
            store.update_metadata(
                task_id,
                {
                    "skill_catalog_query": query or goal,
                    "skill_catalog_shortlist": shortlist_paths,
                    "skill_scan_at": payload.get("source"),
                },
            )
            out["evidence_id"] = ev.id
            out["recorded"] = True
        else:
            out["recorded"] = False
            out["warn"] = "Pass task_id=... or phase/claim gates will BLOCK (overconfidence waiver denied)."
        return _json(out)

    if name == "record_skills_loaded":
        from godkiller_mcp.skill_gates import build_loaded_payload, loaded_gate

        paths = arguments.get("paths") or []
        if len(paths) > 4:
            return _json(
                {
                    "allowed": False,
                    "reason": "Max 4 skills_loaded (brain bloat).",
                    "action": PolicyAction.BLOCK.value,
                }
            )
        if len(paths) < 1:
            return _json(
                {
                    "allowed": False,
                    "reason": "Need at least 1 path after view_file.",
                    "action": PolicyAction.BLOCK.value,
                }
            )
        payload = build_loaded_payload(paths)
        ev = store.submit_evidence(
            task_id=arguments["task_id"],
            evidence_type=EvidenceType.OTHER,
            summary=f"skills_loaded n={len(payload['paths'])}",
            payload=payload,
        )
        store.update_metadata(arguments["task_id"], {"skills_loaded": payload["paths"]})
        ok, reason = loaded_gate(store.get(arguments["task_id"]))
        return _json(
            {
                "allowed": ok,
                "reason": reason,
                "evidence_id": ev.id,
                "paths": payload["paths"],
            }
        )

    if name == "activate_mode":
        mode = arguments["mode"]
        goal = arguments.get("goal") or ""
        payload = modes.activate(
            mode,
            goal,
            kind=arguments.get("kind"),
            slug=arguments.get("slug"),
            plan_phase=int(arguments.get("plan_phase") or 1),
        )
        opened = None
        marathon_state = None
        if arguments.get("open_kernel_task", True) and mode in ("ask", "plan", "debug", "ultradeep"):
            kind = arguments.get("kind") or payload["kind_suggestion"]
            opened_state = store.open_task(
                kind=kind,
                goal=goal or f"{mode} session",
                project_id=arguments.get("project_id") or "default",
            )
            opened = {
                "task_id": opened_state.handle.task_id,
                "kind": opened_state.handle.kind.value,
                "phase": opened_state.handle.phase.value,
                "rubric_id": opened_state.handle.rubric_id,
            }
            payload["task_id"] = opened_state.handle.task_id
            if mode == "ultradeep":
                slug = arguments.get("slug") or f"m_{opened_state.handle.task_id[-8:]}"
                try:
                    mstate = marathon.load(slug)
                except FileNotFoundError:
                    mstate = marathon.init(
                        slug=slug,
                        goal=goal or opened_state.handle.goal,
                        kind=kind,
                        plan_path=arguments.get("plan_path"),
                        task_id=opened_state.handle.task_id,
                    )
                marathon_state = json.loads(mstate.model_dump_json())
                payload["slug"] = slug
                payload["next_wake"] = marathon.next_wake_prompt(slug)
        return _json(
            {
                **payload,
                "opened_task": opened,
                "marathon": marathon_state,
            }
        )

    if name == "gk_memory_query_graph":
        return _json(workflow.query_related(arguments["task_id"]))

    if name == "gk_memory_what_blocked":
        return _json(
            workflow.what_blocked_claim_done(
                arguments["task_id"],
                policy_reason=arguments.get("policy_reason") or "",
            )
        )

    if name == "gk_memory_upsert_episode":
        return _json(
            workflow.upsert_episode(
                arguments["task_id"],
                arguments["summary"],
                arguments.get("payload"),
            )
        )

    if name == "gk_plan_template":
        return _json(plan_os.template(arguments.get("goal") or ""))

    if name == "gk_plan_validate":
        plan = arguments.get("plan") or arguments.get("content") or arguments.get("plan_dict")
        result = plan_os.validate(plan)
        task_id = arguments.get("task_id")
        if task_id:
            patch = {"plan_validation": result}
            if isinstance(plan, dict):
                patch["plan_dict"] = plan
            store.update_metadata(task_id, patch)
            result["task_id"] = task_id
        return _json(result)

    if name == "gk_code_read_full":
        path = Path(arguments["path"])
        if not path.exists():
            return _json({"ok": False, "error": f"missing file: {path}"})
        text = path.read_text(encoding="utf-8", errors="ignore")
        max_chars = int(arguments.get("max_chars") or 200000)
        truncated = len(text) > max_chars
        return _json(
            {
                "ok": True,
                "path": str(path.resolve()),
                "chars": len(text),
                "truncated": truncated,
                "content": text[:max_chars],
            }
        )

    if name == "gk_scan_semgrep":
        return _json(run_semgrep(arguments.get("target_path") or ".", arguments.get("config") or "auto"))

    if name == "gk_browser_navigate":
        return _json(pw_browser.navigate(arguments["url"]))

    if name == "gk_browser_snapshot":
        return _json(pw_browser.snapshot())

    if name == "gk_browser_screenshot":
        res = pw_browser.screenshot(arguments.get("name") or "shot.png")
        if res.get("ok") and arguments.get("task_id"):
            vision_result = vision.analyze_screenshot(res["path"])
            res["vision"] = vision_result.__dict__
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.SCREENSHOT,
                summary=f"browser screenshot {res['path']}",
                payload=res,
                uri=res["path"],
            )
            res["evidence_id"] = ev.id
        return _json(res)

    if name == "gk_browser_click":
        return _json(pw_browser.click(arguments["selector"]))

    if name == "gk_browser_fill":
        return _json(pw_browser.fill(arguments["selector"], arguments["value"]))

    raise ValueError(f"Unknown tool: {name}")


