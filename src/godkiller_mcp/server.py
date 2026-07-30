"""GODKILLER MCP Server — Policy + CodeIntel + Browser + Lesson Memory."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import TextContent, Tool

from godkiller.browser_bridge import BrowserEvidenceBridge, JourneyResult, JourneyStep
from godkiller.code_intel import (
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
from godkiller.evidence_store import EvidenceStore
from godkiller.handoff_docs import SpecFeedbackStore
from godkiller.loop_guard import LoopDetector
from godkiller.marathon import MarathonRelay
from godkiller.memory_lessons import LessonMemory, MemoryTier
from godkiller.modes import MODES, ModeProtocolStore
from godkiller.skill_catalog import build_catalog, filter_catalog, suggest_from_catalog
from godkiller.policy import PolicyEngine, rubric_for_kind
from godkiller.schema import EvidenceType, Phase, PolicyAction, TaskKind
from godkiller.quality_gates import (
    LADDER_LEVELS,
    build_compare_delta,
    build_competitor_scan,
    next_ladder_level,
    run_soak,
    run_visual_critic,
)
from godkiller.verify_bundle import VerifyBundleRunner

ROOT = Path(__file__).resolve().parents[2]
STORE_DIR = ROOT / "arena" / "results" / "tasks"
STORE_DIR.mkdir(parents=True, exist_ok=True)
MARATHON_DIR = ROOT / "arena" / "results" / "marathon"
MARATHON_DIR.mkdir(parents=True, exist_ok=True)
HANDOFF_DIR = ROOT / "arena" / "results" / "handoff"
HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

app = Server("GODKILLER")
store = EvidenceStore(persist_dir=STORE_DIR)
policy = PolicyEngine()
browser = BrowserEvidenceBridge(store, artifact_dir=ROOT / "arena" / "results" / "ui_artifacts")
lessons = LessonMemory(str(ROOT / "lessons.db"))
marathon = MarathonRelay(MARATHON_DIR)
modes = ModeProtocolStore(ROOT / ".agents")
verify_runner = VerifyBundleRunner()
loops = LoopDetector()
handoff = SpecFeedbackStore(HANDOFF_DIR)


def _json(data: Any) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2, default=str))]


@app.list_tools()
async def list_tools() -> List[Tool]:
    return [
        # --- Policy ---
        Tool(
            name="open_task",
            description="Open a GODKILLER task handle with kind-specific rubric.",
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["bugfix", "feature", "refactor"]},
                    "goal": {"type": "string"},
                    "project_id": {"type": "string"},
                },
                "required": ["kind", "goal"],
            },
        ),
        Tool(
            name="propose_hypothesis",
            description="Propose a root-cause hypothesis with support and refute evidence refs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "claim": {"type": "string"},
                    "support_refs": {"type": "array", "items": {"type": "string"}},
                    "refute_refs": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["task_id", "claim"],
            },
        ),
        Tool(
            name="assert_phase",
            description="Advance task phase one step at a time (blocks illegal jumps).",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "phase": {
                        "type": "string",
                        "enum": [p.value for p in Phase],
                    },
                },
                "required": ["task_id", "phase"],
            },
        ),
        Tool(
            name="submit_evidence",
            description="Attach typed evidence to the task Evidence Graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "type": {"type": "string", "enum": [e.value for e in EvidenceType]},
                    "summary": {"type": "string"},
                    "payload": {"type": "object"},
                    "uri": {"type": "string"},
                    "contradicts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["task_id", "type", "summary"],
            },
        ),
        Tool(
            name="evaluate_rubric",
            description="Evaluate process rubric for a task (pass/fail per item).",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        ),
        Tool(
            name="request_claim_done",
            description=(
                "Request completion. Allowed only when rubric + verify_bundle exit 0 "
                "(+ blast_radius for bugfix/refactor) are satisfied. Forced protocol gates apply."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "handoff_slug": {
                        "type": "string",
                        "description": "If set, also require feedback.md passed=true for this slug.",
                    },
                    "require_verify_bundle": {"type": "boolean", "default": True},
                    "require_quality_loop": {
                        "type": "boolean",
                        "default": True,
                        "description": "For feature tasks: require capture/soak/critic/competitor gates.",
                    },
                    "require_competitor_loop": {"type": "boolean", "default": True},
                    "min_ambition_ladder": {
                        "type": "string",
                        "enum": list(LADDER_LEVELS),
                        "default": "L1_presence",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="policy_decide",
            description="Deterministic policy action: CONTINUE|REPLAN|ESCALATE_FRONTIER|STOP|ALLOW_CLAIM_DONE.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        ),
        Tool(
            name="get_task_graph",
            description="Dump full Evidence Graph / task state for a handle.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        ),
        # --- Code Intel ---
        Tool(
            name="get_failing_slice",
            description="Parse test/traceback output into failing-slice evidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "test_output": {"type": "string"},
                    "workspace": {"type": "string"},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["test_output"],
            },
        ),
        Tool(
            name="blast_radius",
            description="Compute symbol blast radius and optionally attach as evidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "symbol": {"type": "string"},
                    "workspace": {"type": "string"},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["symbol", "workspace"],
            },
        ),
        Tool(
            name="check_edit_safe",
            description=(
                "Heuristic edit-safety check; ALSO enforces blast_radius-before-edit gate "
                "when task_id is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "paths": {"type": "array", "items": {"type": "string"}},
                    "workspace": {"type": "string"},
                    "attach": {"type": "boolean", "default": True},
                    "require_blast": {"type": "boolean", "default": True},
                },
                "required": ["paths", "workspace"],
            },
        ),
        # --- Loop Engineering: verify_bundle + loop_detector + handoff ---
        Tool(
            name="verify_bundle",
            description=(
                "Run project verify commands (pytest/npm/cargo/…). "
                "Attaches EXIT_CODE/PASSING_TEST evidence. REQUIRED before claim_done. "
                "Blocks grep-only/hacked verifiers."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "workspace": {"type": "string"},
                    "commands": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional explicit commands; else auto-detect.",
                    },
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["workspace"],
            },
        ),
        Tool(
            name="record_tool_event",
            description=(
                "Record a tool/action for loop + phase-stall detection. "
                "Returns REPLAN or ESCALATE_FRONTIER when Anti is spinning."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "tool": {"type": "string"},
                    "signature": {"type": "string"},
                    "phase": {"type": "string"},
                },
                "required": ["task_id", "tool"],
            },
        ),
        Tool(
            name="loop_status",
            description="Inspect loop detector history for a task.",
            inputSchema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
        ),
        Tool(
            name="write_spec",
            description=(
                "Planner writes spec.md for Builder/Eval. BLOCKED unless search_queries "
                "has enough entries (feature≥5). Local skills do not waive search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "content": {"type": "string"},
                    "goal": {"type": "string"},
                    "search_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Queries you actually ran via search_web (required for gate).",
                    },
                    "kind": {
                        "type": "string",
                        "enum": ["feature", "bugfix", "refactor"],
                        "default": "feature",
                    },
                    "require_search": {"type": "boolean", "default": True},
                    "min_queries": {"type": "integer"},
                },
                "required": ["slug", "content"],
            },
        ),
        Tool(
            name="write_feedback",
            description="Evaluator writes feedback.md after verify; passed=true required for claim soft-gate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "content": {"type": "string"},
                    "score": {"type": "number", "default": 0},
                    "passed": {"type": "boolean", "default": False},
                },
                "required": ["slug", "content"],
            },
        ),
        Tool(
            name="read_handoff",
            description="Read spec.md + feedback.md pack; shows builder/eval/claim readiness.",
            inputSchema={
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"],
            },
        ),
        Tool(
            name="require_spec_gate",
            description="Forced gate: Builder/Eval blocked without spec.md.",
            inputSchema={
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"],
            },
        ),
        # --- Quality / dissatisfaction loop (Phase A) ---
        Tool(
            name="capture_shot",
            description="Register a UI/game screenshot as capture_shot + SCREENSHOT evidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "path": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["task_id", "path"],
            },
        ),
        Tool(
            name="visual_critic",
            description=(
                "Independent visual/quality critic. Placeholder/programmer-art signals → RED. "
                "GREEN required before feature claim. Escalate when RED."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "description": {"type": "string", "description": "What the screenshot/UI shows"},
                    "checklist": {
                        "type": "object",
                        "properties": {
                            "first_screen_readable": {"type": "boolean"},
                            "not_placeholder": {"type": "boolean"},
                            "materials_or_hierarchy_ok": {"type": "boolean"},
                            "reference_delta_acceptable": {"type": "boolean"},
                        },
                    },
                    "findings": {"type": "array", "items": {"type": "string"}},
                    "agent_verdict": {"type": "string", "enum": ["GREEN", "YELLOW", "RED"]},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["task_id", "description"],
            },
        ),
        Tool(
            name="soak_run",
            description="Record a soak/play session (errors, stuck_pct) or run a smoke command. Must pass before feature claim.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "duration_sec": {"type": "number", "default": 30},
                    "errors": {"type": "integer", "default": 0},
                    "stuck_pct": {"type": "number", "default": 0},
                    "notes": {"type": "string"},
                    "command": {"type": "string"},
                    "workspace": {"type": "string"},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="competitor_scan",
            description="Record web/social competitor research. Required before feature claim (dissatisfaction loop).",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "queries": {"type": "array", "items": {"type": "string"}},
                    "competitors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "url": {"type": "string"},
                                "notes": {"type": "string"},
                            },
                        },
                    },
                    "min_required": {"type": "integer", "default": 2},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["task_id", "queries", "competitors"],
            },
        ),
        Tool(
            name="compare_delta",
            description=(
                "Compare ours vs best competitor on axes (positive=win, negative=lose). "
                "still_losing=true blocks claim — keep improving / next ladder level."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "axes": {"type": "object", "additionalProperties": {"type": "number"}},
                    "still_losing": {"type": "boolean"},
                    "notes": {"type": "string"},
                    "best_competitor": {"type": "string"},
                    "attach": {"type": "boolean", "default": True},
                },
                "required": ["task_id", "axes"],
            },
        ),
        Tool(
            name="set_ambition_ladder",
            description="Set ambition ladder level L0_core…L4_dominance after finishing a quality layer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "level": {"type": "string", "enum": list(LADDER_LEVELS)},
                    "advance": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, advance one level from current.",
                    },
                },
                "required": ["task_id"],
            },
        ),
        Tool(
            name="retrieve_lessons_verified",
            description=(
                "Retrieve lessons with side-check before inject (4-tier memory). "
                "Rejects stale / no-overlap / unanchored semantic hits."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                    "tier": {
                        "type": "string",
                        "enum": ["working", "semantic", "episodic", "procedural"],
                    },
                    "task_id": {"type": "string"},
                    "attach": {"type": "boolean", "default": False},
                },
                "required": ["project_id", "query"],
            },
        ),
        # --- Browser bridge ---
        Tool(
            name="register_screenshot",
            description="Register a UI screenshot path as SCREENSHOT evidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "path": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["task_id", "path"],
            },
        ),
        Tool(
            name="register_ui_journey",
            description="Register a UI journey (steps + screenshots) as UI_JOURNEY evidence.",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "name": {"type": "string"},
                    "passed": {"type": "boolean"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string"},
                                "target": {"type": "string"},
                                "expect": {"type": "string"},
                                "screenshot_uri": {"type": "string"},
                            },
                            "required": ["action"],
                        },
                    },
                    "screenshot_uris": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": ["task_id", "name", "passed"],
            },
        ),
        # --- Lesson memory ---
        Tool(
            name="ingest_lesson",
            description="Store a lesson ONLY if task_passed=true (arena/policy success).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "task_id": {"type": "string"},
                    "content": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "task_passed": {"type": "boolean"},
                    "tier": {
                        "type": "string",
                        "enum": ["working", "semantic", "episodic", "procedural"],
                        "default": "semantic",
                    },
                },
                "required": ["project_id", "task_id", "content", "task_passed"],
            },
        ),
        Tool(
            name="retrieve_lessons",
            description="Retrieve top 1–7 lessons for a project/query (policy-capped).",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                    "task_id": {"type": "string"},
                    "attach": {"type": "boolean", "default": False},
                },
                "required": ["project_id", "query"],
            },
        ),
        # --- Marathon Relay (24h across short sessions) ---
        Tool(
            name="marathon_init",
            description="Start a marathon relay slug: STATE.json + PROGRESS.md for /ultradeep multi-session work.",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "goal": {"type": "string"},
                    "kind": {"type": "string", "enum": ["bugfix", "feature", "refactor"]},
                    "plan_path": {"type": "string"},
                    "task_id": {"type": "string"},
                },
                "required": ["slug", "goal"],
            },
        ),
        Tool(
            name="marathon_load_progress",
            description="Load marathon STATE + next wake prompt. Call at start of every /ultradeep continue turn.",
            inputSchema={
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"],
            },
        ),
        Tool(
            name="marathon_save_progress",
            description="Save handoff after finishing ONE phase. Updates STATE.json and PROGRESS.md.",
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "task_id": {"type": "string"},
                    "kernel_phase": {"type": "string"},
                    "current_plan_phase": {"type": "integer"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "search_queries": {"type": "array", "items": {"type": "string"}},
                    "blockers": {"type": "array", "items": {"type": "string"}},
                    "failure_streak": {"type": "integer"},
                    "last_handoff": {"type": "string"},
                    "closed": {"type": "boolean"},
                    "bump_session": {"type": "boolean", "default": True},
                },
                "required": ["slug", "last_handoff"],
            },
        ),
        Tool(
            name="marathon_search_gate",
            description=(
                "Forced epistemics gate: blocks if fewer than min_queries recorded. "
                "Default min = 5 for feature, 3 for bugfix/refactor."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "min_queries": {
                        "type": "integer",
                        "description": "Override; omit to use kind-based default (feature=5).",
                    },
                },
                "required": ["slug"],
            },
        ),
        Tool(
            name="marathon_next_wake",
            description="Return the exact /ultradeep continue prompt for Antigravity schedule tool.",
            inputSchema={
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"],
            },
        ),
        Tool(
            name="marathon_list",
            description="List active marathon slugs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # --- Mode protocols (workflows as MCP — no .agents copy required in target project) ---
        Tool(
            name="list_modes",
            description="List available intelligence modes: ask, plan, debug, ultradeep, verify.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_protocol",
            description="Return the FULL detailed workflow markdown for a mode (ask|plan|debug|ultradeep|verify).",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": list(MODES)},
                },
                "required": ["mode"],
            },
        ),
        Tool(
            name="get_constitution",
            description="Return AGENTS.md constitution text from the godkiller package.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="skill_catalog",
            description=(
                "Thin skill index: name + one-line description + path ONLY (no full SKILL bodies). "
                "REQUIRED before hypothesize/fix — overconfidence ('I know enough') does NOT waive. "
                "Pass task_id to record the scan. Then view_file ≤4 and record_skills_loaded."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Goal or keywords (e.g. '3d retopo game mesh'). Empty = first page only.",
                    },
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
                    "goal": {
                        "type": "string",
                        "description": "If set, also return a shortlist (max 4) to view_file.",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "If set, records skill_catalog evidence on the task (required for gates).",
                    },
                },
            },
        ),
        Tool(
            name="record_skills_loaded",
            description=(
                "After view_file on chosen SKILL.md files, record 1–4 paths. "
                "Required before FIX/claim. Shortlist alone / 'I already know' does NOT count."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 4,
                    },
                },
                "required": ["task_id", "paths"],
            },
        ),
        Tool(
            name="activate_mode",
            description=(
                "REQUIRED entrypoint when .agents is not in the project. "
                "Injects full mode protocol + mandatory rules. Optionally opens a kernel task / marathon."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": list(MODES)},
                    "goal": {"type": "string", "description": "User task / bug / feature goal"},
                    "kind": {"type": "string", "enum": ["bugfix", "feature", "refactor"]},
                    "slug": {"type": "string", "description": "Marathon slug for ultradeep"},
                    "plan_phase": {"type": "integer", "default": 1},
                    "plan_path": {"type": "string"},
                    "open_kernel_task": {
                        "type": "boolean",
                        "default": True,
                        "description": "If true, also call open_task (and marathon_init for ultradeep).",
                    },
                    "project_id": {"type": "string", "default": "default"},
                },
                "required": ["mode"],
            },
        ),
        # --- Alien Assimilation MCP Engines ---
        Tool(
            name="godkiller_repo_map",
            description="Generate a structural AST Repo Map of python classes, functions, and symbols in workspace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_root": {"type": "string", "default": "."},
                    "max_tokens": {"type": "integer", "default": 1000},
                },
            },
        ),
        Tool(
            name="godkiller_hyper_search",
            description="Ultra-fast pattern search across workspace files using ripgrep CLI (with regex fallback).",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex or string pattern"},
                    "search_path": {"type": "string", "default": "."},
                    "max_results": {"type": "integer", "default": 100},
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="godkiller_fast_find",
            description="Rapid file and directory indexing using fd CLI (with os.scandir fallback).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name_pattern": {"type": "string", "description": "File name or extension pattern"},
                    "search_path": {"type": "string", "default": "."},
                    "max_results": {"type": "integer", "default": 100},
                },
                "required": ["name_pattern"],
            },
        ),
        Tool(
            name="godkiller_context_preview",
            description="Styled code snippet preview with line numbers using bat CLI (with line reader fallback).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer", "default": 100},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="godkiller_ast_grep",
            description="Structural AST pattern matching & refactoring using ast-grep CLI (with Python AST fallback).",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "AST pattern (e.g. 'eval($A)', 'print($A)')"},
                    "search_path": {"type": "string", "default": "."},
                    "lang": {"type": "string", "default": "python"},
                    "max_results": {"type": "integer", "default": 50},
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="godkiller_security_scan",
            description="Static security vulnerability scanner (OWASP / CVE check) using snyk CLI (with AST rules fallback).",
            inputSchema={
                "type": "object",
                "properties": {
                    "target_path": {"type": "string", "default": "."},
                    "severity_threshold": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                },
            },
        ),
        Tool(
            name="godkiller_deep_scrape",
            description="Scrape and convert HTML/web pages or API docs into clean LLM-readable Markdown (Firecrawl style).",
            inputSchema={
                "type": "object",
                "properties": {
                    "url_or_html": {"type": "string", "description": "URL or raw HTML string"},
                    "max_length": {"type": "integer", "default": 5000},
                },
                "required": ["url_or_html"],
            },
        ),
        Tool(
            name="godkiller_log_trace",
            description="Parse Python traceback error logs and stack traces into structured JSON (Sentry style).",
            inputSchema={
                "type": "object",
                "properties": {
                    "log_output": {"type": "string", "description": "Raw traceback or log string"},
                },
                "required": ["log_output"],
            },
        ),
        Tool(
            name="godkiller_auto_fix",
            description="Safely apply AST pattern replacement and code refactoring with diff preview.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "pattern": {"type": "string", "description": "AST pattern (e.g. 'old_func($A)')"},
                    "replacement": {"type": "string", "description": "Replacement template (e.g. 'new_func($A)')"},
                    "preview_only": {"type": "boolean", "default": True},
                },
                "required": ["file_path", "pattern", "replacement"],
            },
        ),
        Tool(
            name="godkiller_pipeline",
            description="Autonomous DAG tool execution chain engine for zero-loop multi-step tasks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of step dicts with name, args, and optional depends_on list",
                    },
                },
                "required": ["steps"],
            },
        ),
        Tool(
            name="godkiller_self_heal",
            description="Remediation matrix for automatic tool switching and query self-healing when tasks fail.",
            inputSchema={
                "type": "object",
                "properties": {
                    "failed_tool": {"type": "string"},
                    "error_or_output": {"type": "string"},
                    "task_context": {"type": "object"},
                },
                "required": ["failed_tool", "error_or_output"],
            },
        ),
        Tool(
            name="godkiller_confidence_check",
            description="Evaluates epistemic confidence score (0-100%) and blocks file edits if confidence < 85%.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "known_symbols": {"type": "array", "items": {"type": "string"}},
                    "has_searched": {"type": "boolean", "default": False},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="godkiller_exhaustive_read",
            description="Exhaustive ThreadPool-powered 100% full directory & file reader without skimming.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dir_path": {"type": "string", "description": "Target directory or file path"},
                    "max_files": {"type": "integer", "default": 200},
                },
                "required": ["dir_path"],
            },
        ),
        Tool(
            name="godkiller_auto_skillify",
            description="Auto-generates reusable SKILL.md in .agents/skills/<skill_name>/ upon task completion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "description": {"type": "string"},
                    "instructions": {"type": "string"},
                    "workspace_root": {"type": "string", "default": "."},
                },
                "required": ["skill_name", "description", "instructions"],
            },
        ),
        Tool(
            name="godkiller_council_debate",
            description="Adversarial Multi-Agent Debate (Coder vs Hacker vs Optimizer) to verify safety before file edit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "proposed_code_or_plan": {"type": "string"},
                    "context": {"type": "object"},
                },
                "required": ["proposed_code_or_plan"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
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
        from godkiller.search_gates import assert_phase_search_gate

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
        from godkiller.search_gates import assert_phase_search_gate
        from godkiller.skill_gates import assert_phase_skill_gate

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
        from godkiller.search_gates import normalize_web_search_payload

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
                return _json({"allowed": False, "reason": reason_ui, "action": PolicyAction.BLOCK.value})
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
        return _json(
            {
                "allowed": allowed,
                "reason": reason,
                "action": state.last_policy_action.value if state.last_policy_action else None,
                "results": [r.model_dump() for r in results],
            }
        )

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
        from godkiller.search_gates import write_spec_search_gate

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
        payload = {
            "source": "capture_shot",
            "exists": p.exists(),
            "path": str(p.resolve()) if p.exists() else path,
            "size": p.stat().st_size if p.exists() else 0,
        }
        ev = store.submit_evidence(
            task_id=arguments["task_id"],
            evidence_type=EvidenceType.SCREENSHOT,
            summary=summary if p.exists() else f"{summary} (MISSING FILE: {path})",
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
        from godkiller.skill_gates import build_catalog_evidence_payload

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
            from godkiller.modes import suggest_skills_for_goal

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
        from godkiller.skill_gates import build_loaded_payload, loaded_gate

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

    raise ValueError(f"Unknown tool: {name}")


def main() -> None:
    print("Starting GODKILLER MCP Server...", file=sys.stderr, flush=True)
    from mcp.server.stdio import stdio_server

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
