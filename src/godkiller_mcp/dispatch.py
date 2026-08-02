"""Legacy tool dispatch (internal). Facades in server.py call handle_tool()."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from mcp.types import TextContent

# Shared runtime — handlers should import from runtime_state, not here.
from godkiller_mcp.runtime_state import (  # noqa: F401
    AGENTS_ROOT,
    HANDOFF_DIR,
    MARATHON_DIR,
    ROOT,
    STATE_ROOT,
    STORE_DIR,
    _json,
    browser,
    handoff,
    lessons,
    loops,
    marathon,
    modes,
    plan_os,
    policy,
    pw_browser,
    router,
    secrets,
    store,
    verify_runner,
    vision,
    workflow,
)


async def handle_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Public entry — classify KeyError; soft-fail NameError/TypeError as typed JSON."""
    from godkiller_mcp.fault_probe import PROBE_UNCLEAN_ALLOW, require_probe_clean_or_restore

    if name not in PROBE_UNCLEAN_ALLOW:
        blocked = require_probe_clean_or_restore()
        if blocked:
            return _json(blocked)
    try:
        return await _handle_tool_body(name, arguments or {})
    except KeyError as exc:
        from godkiller_mcp.governance import key_error_payload

        return _json(key_error_payload(exc))
    except NameError as exc:
        return _json(
            {
                "error": "internal_name_error",
                "detail": str(exc),
                "hint": "handler peel bug — report tool name",
                "tool": name,
            }
        )
    except TypeError as exc:
        return _json(
            {
                "error": "type_error",
                "detail": str(exc),
                "hint": "check argument types for this action",
                "tool": name,
            }
        )
    except ValueError as exc:
        # e.g. illegal marathon slug — agent-visible, not a crash
        return _json({"error": "invalid_value", "detail": str(exc), "tool": name})
    except PermissionError as exc:
        return _json({"error": "permission_denied", "detail": str(exc), "tool": name})


async def _handle_tool_body(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    from godkiller_mcp.governance import require_task_for_privileged
    from godkiller_mcp.handlers import REGISTRY, ensure_registered

    blocked = require_task_for_privileged(name, arguments or {})
    if blocked:
        return _json({"ok": False, "allowed": False, "reason": blocked, "action": "block"})

    from godkiller_mcp import dispatch_debug, dispatch_swarm, dispatch_tools, dispatch_view

    for mod in (dispatch_view, dispatch_debug, dispatch_swarm, dispatch_tools):
        handled = await mod.handle(name, arguments)
        if handled is not None:
            return handled

    ensure_registered()
    registered = REGISTRY.get(name)
    if registered is not None:
        return await registered(name, arguments or {})

    if name == "godkiller_route_intent":
        decision = router.route_intent(arguments["prompt"])
        payload = dict(decision.__dict__)
        payload["honest"] = "route_weight is a fixed heuristic, not measured confidence"
        return _json(payload)

    if name == "godkiller_inspect_image":
        from godkiller_mcp.path_sandbox import path_gate_error

        bad = path_gate_error(arguments["path"])
        if bad:
            return _json(bad)
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

    if name == "gk_honesty_status":
        from godkiller_mcp.honesty import build_honesty_status

        detail = bool(arguments.get("detail") or arguments.get("verbose"))
        return _json(build_honesty_status(detail=detail))

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
                from godkiller_mcp.schema import PolicyAction

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
        ui_work = arguments.get("ui_work")
        if ui_work is not None:
            ui_work = bool(ui_work)
        out = plan_os.template(arguments.get("goal") or "", ui_work=ui_work)
        # Fail recipes from lessons → inject into plan (ROI #5)
        try:
            from godkiller_mcp.roi_gates import format_fail_recipes, inject_fail_recipes

            project_id = arguments.get("project_id") or "default"
            query = arguments.get("goal") or arguments.get("query") or ""
            recipes = lessons.retrieve_fail_recipes(
                project_id, query=str(query), limit=int(arguments.get("fail_limit") or 4)
            )
            text = format_fail_recipes(recipes.get("injected") or [])
            out = inject_fail_recipes(out, text)
            out["fail_recipes"] = recipes.get("injected") or []
        except Exception as exc:
            out["fail_recipes_error"] = str(exc)
        return _json(out)

    if name == "gk_plan_validate":
        from godkiller_mcp.governance import plan_digest
        from godkiller_mcp.session_ledger import append_ledger

        plan = arguments.get("plan") or arguments.get("content") or arguments.get("plan_dict")
        ui_work = arguments.get("ui_work")
        if ui_work is not None:
            ui_work = bool(ui_work)
        meta = None
        task_id = arguments.get("task_id")
        if task_id:
            try:
                meta = dict(store.get(task_id).handle.metadata or {})
            except Exception:
                meta = None
        result = plan_os.validate(plan, ui_work=ui_work, metadata=meta)
        if result.get("valid"):
            result["digest"] = plan_digest(plan)
        # Attach fail recipes reminder when validating with a task
        if task_id:
            try:
                from godkiller_mcp.roi_gates import format_fail_recipes

                goal = ""
                if isinstance(plan, dict):
                    goal = str(plan.get("goal") or "")
                recipes = lessons.retrieve_fail_recipes(
                    store.get(task_id).handle.project_id,
                    query=goal,
                    limit=4,
                )
                text = format_fail_recipes(recipes.get("injected") or [])
                if text:
                    result["fail_recipes_reminder"] = text
                    result["fail_recipes"] = recipes.get("injected") or []
            except Exception:
                pass
        if task_id:
            patch = {"plan_validation": result}
            if isinstance(plan, dict):
                patch["plan_dict"] = plan
            if result.get("digest"):
                patch["plan_digest"] = result["digest"]
            if result.get("ui_plan"):
                patch["ui_plan"] = result["ui_plan"]
            store.update_metadata(task_id, patch)
            result["task_id"] = task_id
            try:
                append_ledger(
                    "plan_validate",
                    {
                        "valid": result.get("valid"),
                        "digest": result.get("digest"),
                        "ui_work": (result.get("ui_plan") or {}).get("ui_work"),
                    },
                    task_id=task_id,
                )
            except Exception:
                pass
        return _json(result)

    if name == "gk_code_read_full":
        import asyncio

        from godkiller_mcp.path_sandbox import ensure_under_root, path_gate_error, workspace_root

        raw_path = arguments.get("path")
        if not raw_path:
            return _json({"ok": False, "error": "missing_arg", "fields": ["path"]})
        bad = path_gate_error(raw_path)
        if bad:
            return _json(bad)
        try:
            path = ensure_under_root(raw_path)
            ws = workspace_root()
        except ValueError as exc:
            return _json(
                {
                    "ok": False,
                    "error": "path_outside_workspace",
                    "detail": str(exc),
                    "workspace": str(Path.cwd().resolve()),
                }
            )
        if not path.is_file():
            return _json({"ok": False, "error": f"missing file: {path}", "workspace": str(ws)})

        def _read() -> tuple[str, int]:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            return raw, len(raw)

        text, nchars = await asyncio.to_thread(_read)
        # Default 48k — host context budget; ask offset/paging via max_chars + note
        max_chars = int(arguments.get("max_chars") or 48_000)
        max_chars = max(1, min(max_chars, 200_000))
        offset = max(0, int(arguments.get("offset") or 0))
        chunk = text[offset : offset + max_chars]
        truncated = (offset + len(chunk)) < nchars or offset > 0
        return _json(
            {
                "ok": True,
                "path": str(path.resolve()),
                "chars": nchars,
                "offset": offset,
                "returned_chars": len(chunk),
                "truncated": truncated,
                "next_offset": (offset + len(chunk)) if truncated and (offset + len(chunk)) < nchars else None,
                "content": chunk,
                "workspace": str(ws),
                "paging": "pass offset= + max_chars= to continue; default max_chars=48000",
            }
        )

    if name == "gk_scan_semgrep":
        from godkiller_mcp.path_sandbox import path_gate_error, workspace_root
        from godkiller_mcp.scan_runtime import run_semgrep

        raw = arguments.get("target_path") or "."
        target = str(workspace_root()) if str(raw).strip() in ("", ".") else str(raw)
        bad = path_gate_error(target)
        if bad:
            return _json(bad)
        return _json(run_semgrep(target, arguments.get("config") or "auto"))

    if name == "gk_browser_navigate":
        from godkiller_mcp.browser_preference import gk_browser_gate

        blocked = gk_browser_gate(arguments)
        if blocked:
            return _json(blocked)
        return _json(pw_browser.navigate(arguments["url"]))

    if name == "gk_browser_snapshot":
        from godkiller_mcp.browser_preference import gk_browser_gate

        blocked = gk_browser_gate(arguments)
        if blocked:
            return _json(blocked)
        return _json(pw_browser.snapshot())

    if name == "gk_browser_screenshot":
        from godkiller_mcp.browser_preference import gk_browser_gate

        blocked = gk_browser_gate(arguments)
        if blocked:
            return _json(blocked)
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
        from godkiller_mcp.browser_preference import gk_browser_gate

        blocked = gk_browser_gate(arguments)
        if blocked:
            return _json(blocked)
        return _json(pw_browser.click(arguments["selector"]))

    if name == "gk_browser_fill":
        from godkiller_mcp.browser_preference import gk_browser_gate

        blocked = gk_browser_gate(arguments)
        if blocked:
            return _json(blocked)
        return _json(pw_browser.fill(arguments["selector"], arguments["value"]))

    raise ValueError(f"Unknown tool: {name}")


