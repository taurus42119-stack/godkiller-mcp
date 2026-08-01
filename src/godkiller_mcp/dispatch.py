"""Legacy tool dispatch (internal). Facades in server.py call handle_tool()."""

from __future__ import annotations

import asyncio
import json
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
from godkiller_mcp.modes import ModeProtocolStore
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


class _LazyProxy:
    """Delay heavy/seal-bound construction until first attribute access."""

    __slots__ = ("_factory", "_obj")

    def __init__(self, factory: Any) -> None:
        object.__setattr__(self, "_factory", factory)
        object.__setattr__(self, "_obj", None)

    def _get(self) -> Any:
        obj = object.__getattribute__(self, "_obj")
        if obj is None:
            obj = object.__getattribute__(self, "_factory")()
            object.__setattr__(self, "_obj", obj)
        return obj

    def __getattr__(self, name: str) -> Any:
        return getattr(self._get(), name)


def _make_store() -> EvidenceStore:
    return EvidenceStore(persist_dir=STORE_DIR)


store = _LazyProxy(_make_store)
policy = PolicyEngine()
browser = _LazyProxy(
    lambda: BrowserEvidenceBridge(store._get(), artifact_dir=ui_artifacts_dir(STATE_ROOT))
)
lessons = _LazyProxy(lambda: LessonMemory(str(lessons_db_path(STATE_ROOT))))
marathon = MarathonRelay(MARATHON_DIR)
modes = ModeProtocolStore(AGENTS_ROOT)
verify_runner = VerifyBundleRunner()
loops = LoopDetector()
handoff = SpecFeedbackStore(HANDOFF_DIR)
secrets = ScopeSafeSecretsLoader(Path.cwd() / ".env")
router = EpistemicRouter()
vision = VisionBridge()
plan_os = PlanOS()
workflow = _LazyProxy(lambda: WorkflowGraph(store._get()))
pw_browser = _LazyProxy(
    lambda: PlaywrightBrowser(artifact_dir=ui_artifacts_dir(STATE_ROOT))
)


def _json(data: Any) -> List[TextContent]:
    from godkiller_mcp.compact_io import dumps_payload

    return [TextContent(type="text", text=dumps_payload(data))]


async def handle_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Public entry — classify KeyError; soft-fail NameError/TypeError as typed JSON."""
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
        return _json(decision.__dict__)

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
        return _json(plan_os.template(arguments.get("goal") or "", ui_work=ui_work))

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
        from godkiller_mcp.code_intel import check_edit_safe

        raw_path = arguments.get("path")
        if not raw_path:
            return _json({"ok": False, "error": "missing_arg", "fields": ["path"]})
        workspace = Path.cwd()
        gate = check_edit_safe([str(raw_path)], workspace)
        if not (gate.payload or {}).get("safe"):
            return _json(
                {
                    "ok": False,
                    "error": "path_outside_workspace",
                    "reasons": (gate.payload or {}).get("reasons") or [],
                    "workspace": str(workspace.resolve()),
                }
            )
        resolved = (gate.payload or {}).get("resolved") or []
        path = Path(resolved[0]) if resolved else Path(raw_path)
        if not path.is_file():
            return _json({"ok": False, "error": f"missing file: {path}"})

        def _read() -> tuple[str, int]:
            raw = path.read_text(encoding="utf-8", errors="ignore")
            return raw, len(raw)

        text, nchars = await asyncio.to_thread(_read)
        max_chars = int(arguments.get("max_chars") or 200000)
        truncated = nchars > max_chars
        return _json(
            {
                "ok": True,
                "path": str(path.resolve()),
                "chars": nchars,
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


