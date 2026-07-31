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
from godkiller_mcp import ultradeep_engine as ude
from godkiller_mcp.runtime_paths import (
    package_root,
    resolve_state_root,
    tasks_dir,
    marathon_dir,
    handoff_dir,
    ui_artifacts_dir,
    lessons_db_path,
)

# Mutable state lives under GODKILLER_HOME or cwd/.godkiller — never under site-packages.
STATE_ROOT = resolve_state_root()
STORE_DIR = tasks_dir(STATE_ROOT)
MARATHON_DIR = marathon_dir(STATE_ROOT)
HANDOFF_DIR = handoff_dir(STATE_ROOT)
# Protocols / AGENTS.md still read from package or cwd .agents
ROOT = package_root()
AGENTS_ROOT = Path.cwd() / ".agents"
if not AGENTS_ROOT.exists():
    AGENTS_ROOT = ROOT / ".agents"

store = EvidenceStore(persist_dir=STORE_DIR)
policy = PolicyEngine()
browser = BrowserEvidenceBridge(store, artifact_dir=ui_artifacts_dir(STATE_ROOT))
lessons = LessonMemory(str(lessons_db_path(STATE_ROOT)))
marathon = MarathonRelay(MARATHON_DIR)
modes = ModeProtocolStore(AGENTS_ROOT)
verify_runner = VerifyBundleRunner()
loops = LoopDetector()
handoff = SpecFeedbackStore(HANDOFF_DIR)
secrets = ScopeSafeSecretsLoader(Path.cwd() / ".env")
router = EpistemicRouter()
vision = VisionBridge()
plan_os = PlanOS()
workflow = WorkflowGraph(store)
pw_browser = PlaywrightBrowser(artifact_dir=ui_artifacts_dir(STATE_ROOT))


def _json(data: Any) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


async def handle_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    from godkiller_mcp.governance import require_task_for_privileged

    blocked = require_task_for_privileged(name, arguments or {})
    if blocked:
        return _json({"ok": False, "allowed": False, "reason": blocked, "action": "block"})

    if name == "godkiller_route_intent":
        decision = router.route_intent(arguments["prompt"])
        return _json(decision.__dict__)

    if name == "godkiller_inspect_image":
        result = vision.analyze_screenshot(
            arguments["path"],
            expected_elements=arguments.get("expected_elements"),
        )
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
        # Default: full file contents. Truncate only if caller sets max_chars_per_file.
        max_chars = arguments.get("max_chars_per_file", None)
        engine = ExhaustiveReaderEngine()
        res = engine.read_all(dpath, max_files=mfiles, max_chars_per_file=max_chars)
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
        mode = arguments.get("mode")  # auto|host|api
        prefer_api = bool(arguments.get("prefer_api", False))
        require_llm = bool(arguments.get("require_llm", False))
        rounds = int(arguments.get("rounds", 2))
        engine = CouncilDebateEngine()
        res = engine.debate(
            prop,
            context=ctx,
            mode=mode,
            prefer_api=prefer_api,
            require_llm=require_llm,
            rounds=rounds,
        )
        return _json(res)

    if name == "godkiller_council_submit":
        engine = CouncilDebateEngine()
        res = engine.submit_opinion(
            session_id=arguments["session_id"],
            role=arguments["role"],
            vote=arguments["vote"],
            critique=arguments.get("critique", ""),
            severity=int(arguments.get("severity", 5)),
            must_fix=arguments.get("must_fix"),
        )
        return _json(res)

    if name == "godkiller_council_finalize":
        engine = CouncilDebateEngine()
        res = engine.finalize_host(
            arguments["session_id"],
            advance_round=bool(arguments.get("advance_round", False)),
        )
        return _json(res)

    if name == "godkiller_pipeline":
        steps_arg = arguments["steps"]
        engine = PipelineRunner()
        execute = arguments.get("execute", True)

        async def _exec(tool_name: str, args: Dict[str, Any]):
            return await handle_tool(tool_name, args)

        res = await engine.run_pipeline(steps_arg, executor=_exec if execute else None)
        return _json(res)

    if name == "godkiller_self_heal":
        ftool = arguments["failed_tool"]
        eout = arguments["error_or_output"]
        tctx = arguments.get("task_context", {})
        engine = SelfHealingEngine()
        run_fallback = arguments.get("execute", True)

        async def _exec(tool_name: str, args: Dict[str, Any]):
            return await handle_tool(tool_name, args)

        if run_fallback:
            res = await engine.heal_and_run(ftool, eout, task_context=tctx, executor=_exec)
        else:
            res = engine.heal(ftool, eout, task_context=tctx)
        return _json(res)

    if name == "godkiller_confidence_check":
        fpath = arguments["file_path"]
        ksyms = arguments.get("known_symbols", [])
        hsearched = arguments.get("has_searched", False)
        hit_count = arguments.get("search_hit_count")
        engine = EpistemicConfidenceGate()
        res = engine.evaluate(
            fpath,
            known_symbols=ksyms,
            has_searched=hsearched,
            search_hit_count=hit_count,
        )
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
        cur = store.get(arguments["task_id"])
        ok_s, reason_s = assert_phase_search_gate(cur, Phase.HYPOTHESIZE)
        if ok_s:
            try:
                store.assert_phase(arguments["task_id"], Phase.HYPOTHESIZE)
            except ValueError as exc:
                return _json(
                    {
                        **hyp.model_dump(),
                        "phase_advanced": False,
                        "phase_error": str(exc),
                    }
                )
        else:
            return _json(
                {
                    **hyp.model_dump(),
                    "phase_advanced": False,
                    "phase_blocked": reason_s,
                }
            )
        return _json({**hyp.model_dump(), "phase_advanced": True})

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
        try:
            state = store.assert_phase(arguments["task_id"], arguments["phase"])
        except ValueError as exc:
            return _json(
                {
                    "allowed": False,
                    "reason": str(exc),
                    "action": PolicyAction.BLOCK.value,
                    "phase": cur.handle.phase.value,
                }
            )
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
        try:
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=arguments["type"],
                summary=arguments["summary"],
                payload=payload,
                uri=arguments.get("uri"),
                contradicts=arguments.get("contradicts"),
                server_authored=False,
            )
        except PermissionError as exc:
            return _json(
                {
                    "allowed": False,
                    "error": str(exc),
                    "action": PolicyAction.BLOCK.value,
                }
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
        import os

        state = store.get(arguments["task_id"])
        if state.closed:
            return _json(
                {
                    "allowed": False,
                    "reason": "Task is already closed.",
                    "action": PolicyAction.BLOCK.value,
                }
            )
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
        relax = os.environ.get("GODKILLER_DEV_RELAX", "").strip() == "1"
        require_vb = True if not relax else bool(arguments.get("require_verify_bundle", True))
        allowed, results, reason = policy.request_claim_done(
            state,
            require_verify_bundle=require_vb,
            handoff_feedback_ok=handoff_ok,
            handoff_reason=handoff_reason,
            require_quality_loop=arguments.get("require_quality_loop", True),
            require_competitor_loop=arguments.get("require_competitor_loop", True),
            min_ambition_ladder=arguments.get("min_ambition_ladder") or "L1_presence",
        )
        if allowed:
            try:
                if state.handle.phase != Phase.CLAIM_DONE:
                    store.assert_phase(state.handle.task_id, Phase.CLAIM_DONE)
                    loops.note_phase_advance(state.handle.task_id, Phase.CLAIM_DONE)
            except ValueError as exc:
                return _json(
                    {
                        "allowed": False,
                        "reason": f"Cannot close: {exc}",
                        "action": PolicyAction.BLOCK.value,
                        "results": [r.model_dump() for r in results],
                    }
                )
            store.mark_closed(state.handle.task_id)
            state.last_policy_action = PolicyAction.ALLOW_CLAIM_DONE
            try:
                from godkiller_mcp.session_ledger import append_ledger

                append_ledger(
                    "claim_done",
                    {"allowed": True, "reason": reason},
                    task_id=state.handle.task_id,
                )
            except Exception:
                pass
        else:
            state.last_policy_action = PolicyAction.BLOCK
            state.failure_streak += 1
            try:
                from godkiller_mcp.session_ledger import append_ledger

                append_ledger(
                    "claim_done_blocked",
                    {"allowed": False, "reason": reason},
                    task_id=state.handle.task_id,
                )
            except Exception:
                pass
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
                server_authored=True,
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError as exc:
                out["phase_error"] = str(exc)
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
                payload={**report.to_evidence_payload(), "server_authored": True},
                server_authored=True,
            )
            try:
                store.assert_phase(arguments["task_id"], Phase.LOCALIZE)
            except ValueError as exc:
                out["phase_error"] = str(exc)
            out["evidence_id"] = ev.id
        return _json(out)

    if name == "check_edit_safe":
        task_id = arguments.get("task_id")
        if task_id:
            from godkiller_mcp.governance import plan_always_required

            state = store.get(task_id)
            require_plan = arguments.get("require_plan")
            if require_plan is None:
                require_plan = plan_always_required() or state.handle.phase.value in (
                    "fix",
                    "verify",
                    "claim_done",
                )
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
                                "reason": "write-through-plan: 9-step plan missing/incomplete — gk_meta.plan_validate first",
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
        if not out.get("safe", False):
            return _json(
                {
                    "allowed": False,
                    "safe": False,
                    "reason": "; ".join(out.get("reasons") or ["unsafe paths"]),
                    "action": PolicyAction.BLOCK.value,
                    **out,
                }
            )
        out["allowed"] = True
        # Additive /ultradeep per-file gate (opt-out: require_per_file_gate=false)
        if task_id and arguments.get("require_per_file_gate", True):
            state = store.get(task_id)
            gate = ude.get_gate(state.handle.metadata)
            if gate.get("enabled"):
                ok_f, reason_f = ude.check_edit_paths(gate, arguments["paths"])
                if not ok_f:
                    loops.record(task_id, "check_edit_safe", signature="edit_blocked_per_file", phase=state.handle.phase)
                    return _json(
                        {
                            "allowed": False,
                            "safe": False,
                            "reason": reason_f,
                            "action": PolicyAction.BLOCK.value,
                            "file_gate": ude.status_payload(gate),
                        }
                    )
                out["file_gate"] = reason_f
        if arguments.get("attach", True) and task_id:
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.EDIT_SAFE,
                summary=report.summary,
                payload={**report.to_evidence_payload(), "server_authored": True},
                server_authored=True,
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
                server_authored=True,
            )
            # Always also record exit_code evidence for rubric EXIT_CODE checks
            if result.passed:
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.EXIT_CODE,
                    summary="verify_bundle exit 0",
                    payload=result.to_payload(),
                    server_authored=True,
                )
                try:
                    store.assert_phase(task_id, Phase.VERIFY)
                    loops.note_phase_advance(task_id, Phase.VERIFY)
                except ValueError as exc:
                    out["phase_error"] = str(exc)
            out["evidence_id"] = ev.id
            loops.record(
                task_id,
                "verify_bundle",
                signature=f"verify_bundle:{'pass' if result.passed else 'fail'}",
                phase=store.get(task_id).handle.phase,
            )
        try:
            from godkiller_mcp.session_ledger import append_ledger

            append_ledger(
                "verify_bundle",
                {
                    "passed": result.passed,
                    "result_digest": out.get("result_digest"),
                    "cwd": out.get("cwd"),
                },
                task_id=task_id,
            )
        except Exception:
            pass
        return _json(out)

    if name == "hollow_surface":
        from godkiller_mcp.hollow_surface import scan_hollow_surface

        roots = arguments.get("paths") or arguments.get("roots") or [arguments.get("workspace") or "."]
        report = scan_hollow_surface(roots, max_files=int(arguments.get("max_files") or 200))
        payload = report.to_payload()
        task_id = arguments.get("task_id")
        if task_id and arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=payload["summary"],
                payload=payload,
                server_authored=True,
            )
        try:
            from godkiller_mcp.session_ledger import append_ledger

            append_ledger("hollow_surface", payload, task_id=task_id)
        except Exception:
            pass
        return _json(payload)

    if name == "ledger_tail":
        from godkiller_mcp.session_ledger import read_ledger_tail, verify_ledger

        return _json(
            {
                "verify": verify_ledger(),
                "tail": read_ledger_tail(int(arguments.get("n") or 20)),
            }
        )

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
            screenshot_path=arguments.get("screenshot_path") or arguments.get("path"),
            expected_elements=arguments.get("expected_elements"),
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
                # Enable per-file think→plan→edit gate (additive; opt-out per_file_gate=false)
                enable_pf = arguments.get("per_file_gate", True)
                existing = (mstate.metadata or {}).get("ultradeep_file_gate")
                if isinstance(existing, dict) and existing.get("queue"):
                    gate = ude.get_gate({"ultradeep_file_gate": existing})
                    gate["enabled"] = bool(enable_pf)
                else:
                    gate = ude.empty_file_gate(enabled=bool(enable_pf))
                # Persist on task + marathon metadata
                store.update_metadata(
                    opened_state.handle.task_id,
                    {
                        "ultradeep_file_gate": gate,
                        "mode": "ultradeep",
                        "marathon_slug": slug,
                    },
                )
                mstate = marathon.save(
                    slug,
                    task_id=opened_state.handle.task_id,
                    metadata={"ultradeep_file_gate": gate},
                    last_handoff=(
                        mstate.last_handoff
                        or (
                            "ultradeep armed: ONE phase this turn + per-file think→plan→edit. "
                            "Next: ultradeep_queue_files then ultradeep_think_file."
                        )
                    ),
                    bump_session=False,
                )
                marathon_state = json.loads(mstate.model_dump_json())
                payload["slug"] = slug
                payload["next_wake"] = marathon.next_wake_prompt(slug)
                payload["per_file_gate"] = ude.status_payload(gate)
                payload["power_mode"] = (
                    "200% Cursor-agent tool swarm + legacy ultradeep crucible + marathon pacing"
                )
        return _json(
            {
                **payload,
                "opened_task": opened,
                "marathon": marathon_state,
            }
        )

    if name == "ultradeep_queue_files":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled") and arguments.get("force_enable", True):
            gate["enabled"] = True
        gate = ude.queue_files(
            gate,
            arguments.get("paths") or [],
            replace=bool(arguments.get("replace", False)),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": gate})
        slug = arguments.get("slug") or (state.handle.metadata or {}).get("marathon_slug")
        if slug:
            try:
                marathon.save(
                    slug,
                    metadata={"ultradeep_file_gate": gate},
                    last_handoff=f"Queued {len(gate.get('queue') or [])} files; current={gate.get('current')}",
                    bump_session=False,
                )
            except FileNotFoundError:
                pass
        return _json({"ok": True, **ude.status_payload(gate)})

    if name == "ultradeep_think_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled"):
            gate["enabled"] = True
        result = ude.record_think(
            gate,
            arguments["path"],
            arguments.get("think") or "",
            hypotheses=arguments.get("hypotheses"),
            tools_used=arguments.get("tools_used"),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        if result["ok"]:
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"ultradeep_think:{arguments['path']}",
                payload={
                    "path": arguments["path"],
                    "hypotheses": arguments.get("hypotheses") or [],
                    "tools_used": arguments.get("tools_used") or [],
                    "think_len": len(arguments.get("think") or ""),
                },
            )
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_plan_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        if not gate.get("enabled"):
            gate["enabled"] = True
        result = ude.record_plan(
            gate,
            arguments["path"],
            arguments.get("plan") or "",
            tools_used=arguments.get("tools_used"),
        )
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        if result["ok"]:
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.OTHER,
                summary=f"ultradeep_plan:{arguments['path']}",
                payload={"path": arguments["path"], "plan_len": len(arguments.get("plan") or "")},
            )
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_advance_file":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        result = ude.advance_file(gate, arguments.get("path"))
        store.update_metadata(task_id, {"ultradeep_file_gate": result["gate"]})
        return _json({**result, "status": ude.status_payload(result["gate"])})

    if name == "ultradeep_file_status":
        task_id = arguments["task_id"]
        state = store.get(task_id)
        gate = ude.get_gate(state.handle.metadata)
        return _json(ude.status_payload(gate))

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
        from godkiller_mcp.governance import plan_digest
        from godkiller_mcp.session_ledger import append_ledger

        plan = arguments.get("plan") or arguments.get("content") or arguments.get("plan_dict")
        result = plan_os.validate(plan)
        if result.get("valid"):
            result["digest"] = plan_digest(plan)
        task_id = arguments.get("task_id")
        if task_id:
            patch = {"plan_validation": result}
            if isinstance(plan, dict):
                patch["plan_dict"] = plan
            if result.get("digest"):
                patch["plan_digest"] = result["digest"]
            store.update_metadata(task_id, patch)
            result["task_id"] = task_id
            try:
                append_ledger(
                    "plan_validate",
                    {"valid": result.get("valid"), "digest": result.get("digest")},
                    task_id=task_id,
                )
            except Exception:
                pass
        return _json(result)

    if name == "fault_probe":
        from godkiller_mcp.fault_probe import run_fault_probe
        from godkiller_mcp.session_ledger import append_ledger

        report = run_fault_probe(
            workspace=arguments["workspace"],
            target_file=arguments["target"],
            test_command=arguments.get("test_command") or "python -m pytest -q --tb=no",
            timeout_sec=int(arguments.get("timeout_sec") or 45),
            max_mutants=int(arguments.get("max_mutants") or 3),
        )
        out = report.to_payload()
        task_id = arguments.get("task_id")
        if task_id and arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=out["summary"],
                payload=out,
                server_authored=True,
            )
        try:
            append_ledger("fault_probe", out, task_id=task_id)
        except Exception:
            pass
        return _json(out)

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


