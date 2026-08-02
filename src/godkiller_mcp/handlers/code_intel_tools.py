"""Domain handlers peeled from dispatch (facade names unchanged).

Engines are imported per-action (lazy) to avoid cold-start barrel weight.
"""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.types import TextContent


async def handle(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    import asyncio

    from godkiller_mcp.dispatch import handle_tool
    from godkiller_mcp.path_sandbox import WorkspaceRootError, path_gate_error, workspace_root
    from godkiller_mcp.runtime_state import _json, store
    from godkiller_mcp.schema import EvidenceType

    arguments = arguments or {}

    def _ws_or(raw: str) -> str:
        """Default '.' must be the IDE cwd/workspace — never the installed package tree."""
        if str(raw).strip() not in ("", "."):
            return str(raw)
        try:
            return str(workspace_root())
        except WorkspaceRootError as exc:
            raise ValueError(str(exc)) from exc

    if name == "godkiller_exhaustive_read":
        from godkiller_mcp.code_intel import ExhaustiveReaderEngine
        from godkiller_mcp.roi_gates import symbol_intel_satisfied

        dpath = arguments["dir_path"]
        bad = path_gate_error(dpath)
        if bad:
            return _json(bad)
        state = None
        task_id = arguments.get("task_id")
        if task_id:
            try:
                state = store.get(task_id)
            except Exception:
                state = None
        ok_si, reason_si = symbol_intel_satisfied(arguments, state)
        if not ok_si:
            return _json(
                {
                    "ok": False,
                    "allowed": False,
                    "error": "symbol_intel_required",
                    "reason": reason_si,
                    "hint": (
                        "Call jcodemunch / codebase-memory for ranked symbols, or "
                        "gk_code.map / gk_code.search with task_id, then pass "
                        "symbol_digest=… into read_all"
                    ),
                }
            )
        mfiles = arguments.get("max_files", ExhaustiveReaderEngine.DEFAULT_MAX_FILES)
        max_chars = arguments.get(
            "max_chars_per_file", ExhaustiveReaderEngine.DEFAULT_MAX_CHARS_PER_FILE
        )
        engine = ExhaustiveReaderEngine()
        res = await asyncio.to_thread(
            engine.read_all, dpath, max_files=mfiles, max_chars_per_file=max_chars
        )
        if isinstance(res, dict):
            res.setdefault("symbol_intel", reason_si)
        return _json(res)

    if name == "godkiller_auto_skillify":
        from godkiller_mcp.code_intel import AutoSkillifyEngine

        sname = arguments["skill_name"]
        sdesc = arguments["description"]
        sinst = arguments["instructions"]
        wroot = arguments.get("workspace_root", ".")
        bad = path_gate_error(wroot)
        if bad:
            return _json(bad)
        engine = AutoSkillifyEngine()
        res = engine.skillify(sname, sdesc, sinst, workspace_root=wroot)
        return _json(res)

    if name == "godkiller_council_debate":
        from godkiller_mcp.code_intel import CouncilDebateEngine

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
        from godkiller_mcp.code_intel import CouncilDebateEngine

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
        from godkiller_mcp.code_intel import CouncilDebateEngine

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
        from godkiller_mcp.code_intel import PipelineRunner

        steps_arg = arguments["steps"]
        engine = PipelineRunner()
        execute = arguments.get("execute", True)

        async def _exec(tool_name: str, args: Dict[str, Any]):
            return await handle_tool(tool_name, args)

        res = await engine.run_pipeline(steps_arg, executor=_exec if execute else None)
        return _json(res)

    if name == "godkiller_self_heal":
        from godkiller_mcp.code_intel import SelfHealingEngine

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
        from godkiller_mcp.code_intel import EpistemicConfidenceGate

        fpath = arguments["file_path"]
        bad = path_gate_error(fpath)
        if bad:
            return _json(bad)
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
        res.pop("confidence", None)
        res.pop("confidence_pct", None)
        res.setdefault("label", "edit_readiness_metrics")
        res.setdefault(
            "honest",
            "edit_readiness_metrics heuristic — not measured confidence",
        )
        return _json(res)

    if name == "godkiller_deep_scrape":
        from godkiller_mcp.code_intel import DeepScrapeEngine

        u_or_h = arguments["url_or_html"]
        mlength = arguments.get("max_length", 5000)
        engine = DeepScrapeEngine()
        res = engine.scrape(u_or_h, max_length=mlength)
        return _json(res)

    if name == "godkiller_log_trace":
        from godkiller_mcp.code_intel import LogTraceEngine

        lout = arguments["log_output"]
        engine = LogTraceEngine()
        res = engine.parse_log(lout)
        return _json(res)

    if name == "godkiller_auto_fix":
        from godkiller_mcp.code_intel import AutoFixEngine
        from godkiller_mcp.ship_mode import relax_enabled

        fpath = arguments["file_path"]
        bad = path_gate_error(fpath)
        if bad:
            return _json(bad)
        pat = arguments["pattern"]
        repl = arguments["replacement"]
        prev_only = arguments.get("preview_only", True)

        if not relax_enabled():
            prev_only = True
        engine = AutoFixEngine()
        res = engine.fix(fpath, pattern=pat, replacement=repl, preview_only=prev_only)
        if not prev_only and not relax_enabled():
            res = {**(res if isinstance(res, dict) else {"result": res}), "forced_preview": True}
        return _json(res)

    if name == "godkiller_ast_grep":
        from godkiller_mcp.code_intel import AstGrepEngine

        pat = arguments["pattern"]
        spath = arguments.get("search_path", ".")
        target = _ws_or(spath)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        lang = arguments.get("lang", "python")
        mresults = arguments.get("max_results", 50)
        engine = AstGrepEngine()
        res = engine.search(pat, search_path=target, lang=lang, max_results=mresults)
        return _json(res)

    if name == "godkiller_security_scan":
        from godkiller_mcp.code_intel import SecurityScanEngine

        tpath = arguments.get("target_path", ".")
        target = _ws_or(tpath)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        sthreshold = arguments.get("severity_threshold", "medium")
        engine = SecurityScanEngine()
        res = engine.scan(target_path=target, severity_threshold=sthreshold)
        return _json(res)

    if name == "godkiller_repo_map":
        from godkiller_mcp.code_intel import RepoMapGenerator
        from godkiller_mcp.roi_gates import stamp_symbol_intel

        wroot = arguments.get("workspace_root", ".")
        target = _ws_or(wroot)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        mtokens = arguments.get("max_tokens", 1000)
        generator = RepoMapGenerator(target)
        map_text = await asyncio.to_thread(generator.get_repo_map, max_tokens=mtokens)
        stamp_symbol_intel(
            store,
            arguments.get("task_id"),
            source="repo_map",
            digest=map_text[:2000] if isinstance(map_text, str) else str(map_text)[:2000],
        )
        return [TextContent(type="text", text=map_text)]

    if name == "godkiller_hyper_search":
        from godkiller_mcp.code_intel import HyperSearchEngine
        from godkiller_mcp.roi_gates import stamp_symbol_intel

        pat = arguments["pattern"]
        spath = arguments.get("search_path", ".")
        target = _ws_or(spath)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        mresults = arguments.get("max_results", 100)
        searcher = HyperSearchEngine()
        res = searcher.search(pat, search_path=target, max_results=mresults)
        digest = pat
        if isinstance(res, dict):
            hits = res.get("hits") or res.get("matches") or res.get("results") or []
            digest = f"{pat} :: {str(hits)[:1500]}"
        else:
            digest = f"{pat} :: {str(res)[:1500]}"
        stamp_symbol_intel(
            store, arguments.get("task_id"), source="hyper_search", digest=digest
        )
        return _json(res)

    if name == "godkiller_fast_find":
        from godkiller_mcp.code_intel import FastFindEngine

        npat = arguments["name_pattern"]
        spath = arguments.get("search_path", ".")
        target = _ws_or(spath)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        mresults = arguments.get("max_results", 100)
        finder = FastFindEngine()
        res = finder.find(npat, search_path=target, max_results=mresults)
        return _json(res)

    if name == "godkiller_context_preview":
        from godkiller_mcp.code_intel import ContextPreviewEngine

        fpath = arguments["file_path"]
        bad = path_gate_error(fpath)
        if bad:
            return _json(bad)
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

    for tool in [
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
    ]:
        reg(tool, _entry)
