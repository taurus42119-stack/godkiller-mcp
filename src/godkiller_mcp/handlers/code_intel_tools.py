"""Domain handlers peeled from dispatch (facade names unchanged)."""
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
    if name == "godkiller_exhaustive_read":
        dpath = arguments["dir_path"]
        mfiles = arguments.get("max_files", ExhaustiveReaderEngine.DEFAULT_MAX_FILES)
        # Default: capped per-file chars (raise explicitly for full dumps).
        max_chars = arguments.get(
            "max_chars_per_file", ExhaustiveReaderEngine.DEFAULT_MAX_CHARS_PER_FILE
        )
        engine = ExhaustiveReaderEngine()
        res = await asyncio.to_thread(
            engine.read_all, dpath, max_files=mfiles, max_chars_per_file=max_chars
        )
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
        task_id = arguments.get("task_id")
        if task_id and arguments.get("attach", True) and res.get("verdict") not in (
            None,
            "COUNCIL_ERROR",
            "COUNCIL_IN_PROGRESS",
        ):
            payload = {**res, "source": "council_finalize", "server_authored": True}
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=f"council {res.get('verdict')}",
                payload=payload,
                server_authored=True,
            )
            res["evidence_attached"] = True
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
        from godkiller_mcp.ship_mode import relax_enabled

        if not relax_enabled():
            prev_only = True
        engine = AutoFixEngine()
        res = engine.fix(fpath, pattern=pat, replacement=repl, preview_only=prev_only)
        if not prev_only and not relax_enabled():
            res = {**(res if isinstance(res, dict) else {"result": res}), "forced_preview": True}
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
        map_text = await asyncio.to_thread(generator.get_repo_map, max_tokens=mtokens)
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


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['godkiller_exhaustive_read', 'godkiller_auto_skillify', 'godkiller_council_debate', 'godkiller_council_submit', 'godkiller_council_finalize', 'godkiller_pipeline', 'godkiller_self_heal', 'godkiller_confidence_check', 'godkiller_deep_scrape', 'godkiller_log_trace', 'godkiller_auto_fix', 'godkiller_ast_grep', 'godkiller_security_scan', 'godkiller_repo_map', 'godkiller_hyper_search', 'godkiller_fast_find', 'godkiller_context_preview']:
        reg(tool, _entry)
