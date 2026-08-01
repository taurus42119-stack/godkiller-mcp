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
    from godkiller_mcp.browser_bridge import JourneyResult, JourneyStep
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
    from godkiller_mcp.memory_lessons import MemoryTier
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
    from godkiller_mcp.path_sandbox import path_gate_error

    if name == "capture_shot":
        path = arguments["path"]
        bad = path_gate_error(path)
        if bad:
            return _json(bad)
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
        shot = arguments.get("screenshot_path") or arguments.get("path")
        if shot:
            bad = path_gate_error(shot)
            if bad:
                return _json(bad)
        state = store.get(arguments["task_id"])
        kind = arguments.get("kind") or state.handle.kind.value
        result = run_visual_critic(
            kind=kind,
            description=arguments["description"],
            checklist=arguments.get("checklist"),
            agent_verdict=arguments.get("agent_verdict"),
            findings=arguments.get("findings"),
            screenshot_path=shot,
            expected_elements=arguments.get("expected_elements"),
        )
        out = result.to_payload()
        if arguments.get("attach", True):
            payload = {**result.to_payload(), "source": "visual_critic", "server_authored": True}
            ev = store.submit_evidence(
                task_id=arguments["task_id"],
                evidence_type=EvidenceType.OTHER if result.verdict.value != "GREEN" else EvidenceType.LOG,
                summary=result.summary,
                payload=payload,
                server_authored=True,
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
                payload={**result.to_payload(), "server_authored": True},
                server_authored=True,
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
                summary=f"competitor_scan n={len(result.competitors)} urls={result._valid_urls} (agent_supplied)",
                payload=out,
                server_authored=False,
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
                    "compare_delta ceremony PASS (unattested)"
                    if result.passed
                    else "compare_delta still losing — continue ladder"
                ),
                payload=out,
                server_authored=False,
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
        bad = path_gate_error(arguments["path"])
        if bad:
            return _json(bad)
        ev = browser.register_screenshot(
            arguments["task_id"],
            arguments["path"],
            arguments.get("summary", "UI screenshot evidence"),
            step_id=arguments.get("step_id") or arguments.get("step"),
            source=arguments.get("source"),
        )
        return _json(ev.model_dump())

    if name == "visual_step":
        from godkiller_mcp.visual_sequence_gate import (
            DEFAULT_STEP_IDS,
            evaluate_visual_sequence,
            min_visual_shots,
            watermark_elements_rejected,
        )

        task_id = arguments["task_id"]
        path = arguments["path"]
        bad = path_gate_error(path)
        if bad:
            return _json(bad)
        step_id = str(arguments.get("step_id") or arguments.get("step") or "").strip()
        if not step_id:
            return _json(
                {
                    "ok": False,
                    "error": "step_id required (e.g. 01_boot … 10_final_frame)",
                    "suggested_step_ids": list(DEFAULT_STEP_IDS),
                }
            )
        expected = arguments.get("expected_elements") or []
        if isinstance(expected, str):
            expected = [expected]
        expected = [str(x).strip() for x in expected if str(x).strip()]
        if not expected:
            return _json(
                {
                    "ok": False,
                    "error": "expected_elements>=1 required so AI visual_critic can inspect the shot",
                    "step_id": step_id,
                }
            )
        wm_err = watermark_elements_rejected(expected)
        if wm_err:
            return _json({"ok": False, "error": wm_err, "step_id": step_id})
        shot = browser.register_screenshot(
            task_id,
            path,
            arguments.get("summary") or f"visual_step {step_id}",
            step_id=step_id,
            source="visual_step",
        )
        state = store.get(task_id)
        kind = arguments.get("kind") or state.handle.kind.value
        result = run_visual_critic(
            kind=kind,
            description=arguments.get("description")
            or f"Visual QA step {step_id}: inspect running UI/game frame",
            checklist=arguments.get("checklist"),
            agent_verdict=arguments.get("agent_verdict"),
            findings=arguments.get("findings"),
            screenshot_path=path,
            expected_elements=expected,
        )
        out = result.to_payload()
        payload = {
            **result.to_payload(),
            "source": "visual_critic",
            "server_authored": True,
            "step_id": step_id,
            "screenshot_path": str(Path(path).resolve()) if Path(path).exists() else path,
        }
        ev = store.submit_evidence(
            task_id=task_id,
            evidence_type=EvidenceType.OTHER if result.verdict.value != "GREEN" else EvidenceType.LOG,
            summary=f"{result.summary} [step={step_id}]",
            payload=payload,
            server_authored=True,
        )
        seq = evaluate_visual_sequence(store.get(task_id))
        loops.record(task_id, "visual_step", signature=f"visual_step:{step_id}:{result.verdict.value}")
        return _json(
            {
                "ok": result.verdict.value == "GREEN",
                "step_id": step_id,
                "screenshot_evidence_id": shot.id,
                "critic_evidence_id": ev.id,
                "critic": out,
                "sequence": seq,
                "min_shots": min_visual_shots(state.handle.metadata or {}),
                "instruction": seq.get("order"),
            }
        )

    if name == "visual_sequence_status":
        from godkiller_mcp.visual_sequence_gate import evaluate_visual_sequence

        state = store.get(arguments["task_id"])
        return _json(evaluate_visual_sequence(state))

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
        raw_tier = arguments.get("tier") or MemoryTier.SEMANTIC
        tier = raw_tier.value if isinstance(raw_tier, MemoryTier) else str(raw_tier)
        lesson = lessons.ingest_lesson(
            project_id=arguments["project_id"],
            task_id=arguments["task_id"],
            content=arguments["content"],
            tags=arguments.get("tags"),
            evidence_ids=arguments.get("evidence_ids"),
            task_passed=bool(arguments["task_passed"]),
            tier=tier,
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


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['capture_shot', 'visual_critic', 'soak_run', 'competitor_scan', 'compare_delta', 'set_ambition_ladder', 'retrieve_lessons_verified', 'register_screenshot', 'visual_step', 'visual_sequence_status', 'register_ui_journey', 'ingest_lesson', 'retrieve_lessons', 'marathon_init', 'marathon_load_progress', 'marathon_save_progress', 'marathon_search_gate', 'marathon_next_wake', 'marathon_list']:
        reg(tool, _entry)
