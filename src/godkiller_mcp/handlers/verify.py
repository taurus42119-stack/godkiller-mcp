"""Domain handlers peeled from dispatch (facade names unchanged)."""
from __future__ import annotations

from typing import Any, Dict, List

from mcp.types import TextContent


async def handle(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    from godkiller_mcp.runtime_state import (
        _json,
        store,
        policy,
        loops,
        verify_runner,
        lessons,
        handoff,
        browser,
        vision,
        marathon,
        modes,
        workflow,
        plan_os,
        STATE_ROOT,
        STORE_DIR,
    )
    from godkiller_mcp.schema import EvidenceType, Phase, PolicyAction, TaskKind
    from godkiller_mcp.policy import rubric_for_kind
    import asyncio
    from pathlib import Path

    arguments = arguments or {}
    if name == "verify_bundle":
        from godkiller_mcp.freshness import material_hash
        from godkiller_mcp.path_sandbox import ensure_under_root, path_gate_error

        ws_raw = arguments["workspace"]
        bad = path_gate_error(ws_raw)
        if bad:
            return _json(bad)
        try:
            ws = str(ensure_under_root(ws_raw))
        except ValueError as exc:
            return _json(
                {
                    "ok": False,
                    "error": "path_outside_workspace",
                    "detail": str(exc),
                }
            )
        result = verify_runner.run(
            ws,
            arguments.get("commands"),
        )
        out = result.to_payload()
        task_id = arguments.get("task_id")
        # Critic-proof: always bind freshness to the workspace tree — never agent decoy paths alone
        mat = material_hash([ws], workspace=ws)
        out["material_hash"] = mat["material_hash"]
        out["material_files"] = mat["files"]
        out["material_file_count"] = mat["file_count"]
        out["material_scope"] = "workspace"
        out["complete"] = mat.get("complete", True)
        out["truncated"] = mat.get("truncated", False)
        out["manifest_hash"] = mat.get("manifest_hash")
        out["cwd"] = ws
        out["total_code_files"] = mat.get("total_code_files")
        if arguments.get("attach", True) and task_id:
            # Lint-only green must NOT mint PASSING_TEST (claim-grade)
            if result.passed and result.is_test_suite and not result.hack_blocked:
                ev_type = EvidenceType.PASSING_TEST
            else:
                ev_type = EvidenceType.EXIT_CODE
            ev = store.submit_evidence(
                task_id=task_id,
                evidence_type=ev_type,
                summary=result.summary,
                payload=dict(out),
                server_authored=True,
            )
            # Always also record exit_code evidence for rubric EXIT_CODE checks
            if result.passed:
                store.submit_evidence(
                    task_id=task_id,
                    evidence_type=EvidenceType.EXIT_CODE,
                    summary="verify_bundle exit 0",
                    payload=dict(out),
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
            from godkiller_mcp.repair_wake import (
                clear_after_verify_pass,
                mark_repair_required,
            )

            if result.passed and not result.hack_blocked:
                repaired = clear_after_verify_pass(store.get(task_id).handle.metadata)
                store.update_metadata(task_id, {"repair_wake": repaired})
                out["repair_wake"] = repaired
            elif not result.passed or result.hack_blocked:
                armed = mark_repair_required(
                    store.get(task_id).handle.metadata,
                    reason=result.summary or "verify_bundle failed",
                    source="verify_bundle",
                )
                store.update_metadata(task_id, {"repair_wake": armed})
                out["repair_wake"] = armed
                out["next"] = (
                    "verify failed — call ultradeep_repair_wake (diagnosis + ≥3 hypotheses) "
                    "before edit_safe; gk_code.self_heal remains available for tool fallback"
                )
        try:
            from godkiller_mcp.session_ledger import append_ledger

            append_ledger(
                "verify_bundle",
                {
                    "passed": result.passed,
                    "result_digest": out.get("result_digest"),
                    "material_hash": out.get("material_hash"),
                    "cwd": out.get("cwd"),
                },
                task_id=task_id,
            )
        except Exception:
            pass
        return _json(out)

    if name == "hollow_surface":
        from godkiller_mcp.hollow_surface import scan_hollow_surface
        from godkiller_mcp.path_sandbox import gate_paths

        roots = arguments.get("paths") or arguments.get("roots") or [
            arguments.get("workspace") or "."
        ]
        if isinstance(roots, str):
            roots = [roots]
        resolved, err = gate_paths(list(roots))
        if err:
            return _json(err)
        report = scan_hollow_surface(
            [str(p) for p in (resolved or [])],
            max_files=int(arguments.get("max_files") or 200),
        )
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
            if not report.clean:
                from godkiller_mcp.repair_wake import mark_repair_required

                armed = mark_repair_required(
                    store.get(task_id).handle.metadata,
                    reason=payload.get("summary") or "hollow_surface unclean",
                    source="hollow_surface",
                )
                store.update_metadata(task_id, {"repair_wake": armed})
                payload["repair_wake"] = armed
        try:
            from godkiller_mcp.session_ledger import append_ledger

            append_ledger("hollow_surface", payload, task_id=task_id)
        except Exception:
            pass
        return _json(payload)

    if name == "exit_checklist":
        from godkiller_mcp.exit_checklist import build_exit_checklist

        state = store.get(arguments["task_id"])
        report = build_exit_checklist(
            state,
            workspace=arguments.get("workspace"),
            min_ambition_ladder=arguments.get("min_ambition_ladder") or "L1_presence",
        )
        # Persist as server evidence so claim_done can require directive=pass
        payload = {
            **report,
            "source": "exit_checklist",
            "server_authored": True,
        }
        if arguments.get("attach", True):
            store.submit_evidence(
                task_id=state.handle.task_id,
                evidence_type=EvidenceType.LOG,
                summary=f"exit_checklist {report['directive']}",
                payload=payload,
                server_authored=True,
            )
        try:
            from godkiller_mcp.session_ledger import append_ledger

            append_ledger(
                "exit_checklist",
                {
                    "directive": report["directive"],
                    "blocking": report["blocking"],
                    "score": (report.get("stage_board") or {}).get("score"),
                    "current": (report.get("stage_board") or {}).get("current"),
                    "profile": report["profile"],
                },
                task_id=state.handle.task_id,
            )
        except Exception:
            pass
        return _json(report)

    if name == "ledger_tail":
        from godkiller_mcp.session_ledger import read_ledger_tail, verify_ledger

        return _json(
            {
                "verify": verify_ledger(),
                "tail": read_ledger_tail(int(arguments.get("n") or 20)),
            }
        )

    if name == "fault_probe":
        from godkiller_mcp.fault_probe import run_fault_probe
        from godkiller_mcp.session_ledger import append_ledger

        report = run_fault_probe(
            workspace=arguments["workspace"],
            target_file=arguments.get("target"),
            targets=arguments.get("targets"),
            test_command=arguments.get("test_command") or "python -m pytest -q --tb=no",
            timeout_sec=int(arguments.get("timeout_sec") or 45),
            max_mutants=int(arguments.get("max_mutants") or 8),
            max_per_file=int(arguments.get("max_per_file") or 6),
        )
        out = report.to_payload()
        out["cwd"] = str(Path(arguments["workspace"]).resolve())
        out["material_files"] = [
            {"path": t} for t in (out.get("targets") or [])
        ]
        task_id = arguments.get("task_id")
        if task_id and arguments.get("attach", True):
            store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.LOG,
                summary=out["summary"],
                payload=out,
                server_authored=True,
            )
            survivors = out.get("survivors") or []
            if out.get("clean") is False or (isinstance(survivors, list) and len(survivors) > 0):
                from godkiller_mcp.repair_wake import mark_repair_required

                armed = mark_repair_required(
                    store.get(task_id).handle.metadata,
                    reason=out.get("summary") or "fault_probe survivors",
                    source="fault_probe",
                )
                store.update_metadata(task_id, {"repair_wake": armed})
                out["repair_wake"] = armed
        try:
            append_ledger("fault_probe", out, task_id=task_id)
        except Exception:
            pass
        return _json(out)


    raise ValueError("handler %r not in this module" % (name,))


def register() -> None:
    from godkiller_mcp.handlers import register as reg

    async def _entry(n: str, a: Dict[str, Any]) -> List[TextContent]:
        return await handle(n, a)

    for tool in ['verify_bundle', 'hollow_surface', 'exit_checklist', 'ledger_tail', 'fault_probe']:
        reg(tool, _entry)
