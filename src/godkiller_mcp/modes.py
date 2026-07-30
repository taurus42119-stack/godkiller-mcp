"""Mode protocols served via MCP (activate_mode / get_protocol).

Loads the detailed Core-4 workflow markdown from .agents/workflows so any
project can get full ask/plan/debug/ultradeep intelligence without copying
.agents — as long as the model calls activate_mode first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

MODES = ("ask", "plan", "debug", "ultradeep", "verify")

MODE_TO_FILE = {
    "ask": "ask.md",
    "plan": "plan.md",
    "debug": "debug.md",
    "ultradeep": "ultradeep.md",
    "verify": "verify.md",
}

MODE_DEFAULT_KIND = {
    "ask": "feature",
    "plan": "feature",
    "debug": "bugfix",
    "ultradeep": "feature",
    "verify": "feature",
}

# Keyword → skill paths Anti MUST view_file (not optional). Max ~4 per match set.
SKILL_ROUTES: List[tuple] = [
    (
        ("3d", "mesh", "model", "gltf", "glb", "blender", "zbrush", "rig", "retopo", "uv ", "sculpt", "three.js", "threejs", "unity", "unreal", "prop", "character mesh"),
        [
            ".agents/skills/game-development/SKILL.md",
            ".agents/skills/game-ready-3d-pipeline/SKILL.md",
        ],
        ".agents/agent/game-developer.md",
    ),
    (
        ("game", "phaser", "pixi", "godot", "gameplay"),
        [".agents/skills/game-development/SKILL.md"],
        ".agents/agent/game-developer.md",
    ),
    (
        ("ui", "frontend", "css", "react", "dashboard", "figma", "landing", "slop", "taste", "portfolio", "redesign"),
        [
            ".agents/skills/design-taste-frontend/SKILL.md",
            ".agents/skills/addyosmani-skills/skills/frontend-ui-engineering/SKILL.md",
            ".agents/skills/premium-ui-animations/SKILL.md",
        ],
        None,
    ),
    (
        ("security", "auth", "owasp", "xss", "sql inject"),
        [".agents/skills/security-and-hardening/SKILL.md"],
        None,
    ),
]


def suggest_skills_for_goal(goal: str) -> Dict[str, Any]:
    g = (goal or "").lower()
    paths: List[str] = []
    agents: List[str] = []
    matched: List[str] = []
    for keywords, skill_paths, agent_path in SKILL_ROUTES:
        if any(k in g for k in keywords):
            matched.extend(keywords[:3])
            for p in skill_paths:
                if p not in paths:
                    paths.append(p)
            if agent_path and agent_path not in agents:
                agents.append(agent_path)
    # Cap to avoid context dump
    return {
        "must_view_file": paths[:4],
        "must_view_agent": agents[:2],
        "matched": bool(paths),
        "note": (
            "Anti MUST view_file these paths this turn. Skills do NOT auto-inject — "
            "forgetting them is a protocol violation."
            if paths
            else "No domain route matched; Skill-Scan still required from <skills> list."
        ),
    }


class ModeProtocolStore:
    def __init__(self, agents_root: Path):
        self.agents_root = agents_root
        self.workflows_dir = agents_root / "workflows"
        self.agents_md = agents_root / "AGENTS.md"

    def list_modes(self) -> List[Dict[str, str]]:
        out = []
        for mode in MODES:
            path = self.workflows_dir / MODE_TO_FILE[mode]
            out.append(
                {
                    "mode": mode,
                    "available": path.exists(),
                    "path": str(path),
                    "default_kind": MODE_DEFAULT_KIND[mode],
                }
            )
        return out

    def get_protocol(self, mode: str) -> str:
        mode = mode.lower().strip().lstrip("/")
        if mode not in MODE_TO_FILE:
            raise ValueError(f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}")
        path = self.workflows_dir / MODE_TO_FILE[mode]
        if not path.exists():
            raise FileNotFoundError(f"Protocol file missing: {path}")
        return path.read_text(encoding="utf-8")

    def get_constitution(self) -> str:
        if not self.agents_md.exists():
            return "# AGENTS.md missing\nFollow godkiller tools and activate_mode protocols."
        return self.agents_md.read_text(encoding="utf-8")

    def activate(
        self,
        mode: str,
        goal: str = "",
        *,
        kind: Optional[str] = None,
        slug: Optional[str] = None,
        plan_phase: int = 1,
    ) -> Dict[str, Any]:
        mode = mode.lower().strip().lstrip("/")
        protocol = self.get_protocol(mode)
        constitution_excerpt = self._constitution_excerpt()
        resolved_kind = kind or MODE_DEFAULT_KIND.get(mode, "feature")
        skill_hints = suggest_skills_for_goal(goal)

        # Progressive: thin shortlist from catalog (descriptions only), not full bodies
        try:
            from godkiller.skill_catalog import build_catalog, suggest_from_catalog

            skills_root = self.agents_root / "skills"
            catalog = build_catalog(skills_root) if skills_root.is_dir() else []
            shortlist_pack = suggest_from_catalog(
                catalog,
                goal,
                limit=4,
                forced_paths=skill_hints.get("must_view_file") or [],
            )
        except Exception:
            shortlist_pack = {
                "shortlist": [],
                "shortlist_paths": skill_hints.get("must_view_file") or [],
                "rule": "skill_catalog unavailable; Skill-Scan manually.",
                "max_view_file": 4,
            }

        mandatory = [
            "SUPREME LAW: applies to EVERY user task (game, software, hardware, web, design, data, other) — domain never lowers the bar.",
            "You MUST follow the protocol markdown below literally for this turn.",
            "Do not skip forced search / phase / evidence steps.",
            "Use GODKILLER tools named in the protocol when available.",
            "Before claim_done: verify_bundle must exit 0 (Ralph gate).",
            "Before editing code: blast_radius then check_edit_safe.",
            "Call record_tool_event on repeated actions; obey REPLAN/ESCALATE.",
            "Prefer retrieve_lessons_verified over raw retrieve_lessons.",
            "Always: competitor_scan → compare_delta + ambition_ladder for features; never claim while still_losing.",
            "Visual/UI/design/hardware-photo surfaces: capture_shot → soak_run → visual_critic GREEN when applicable.",
            "Non-visual (API/library/CLI): metadata surface=api or require_visual=false — competitor+search still required.",
            "Placeholders are failures not milestones. Advance ambition_ladder in order (L0→L4).",
            "Forced search: submit_evidence web_search queries OR marathon_save_progress — skills never waive search.",
            "Skills do NOT auto-load. Prefer skill_catalog(query=goal, task_id=...) then view_file ≤4 then record_skills_loaded.",
            "ANTI-OVERCONFIDENCE: FORBIDDEN to skip skill_catalog because you 'already know enough'. Shortlist from activate_mode alone does NOT waive gates.",
        ]
        if shortlist_pack.get("shortlist_paths"):
            mandatory.append(
                "Suggested shortlist (choose ≤4, view_file those): "
                + ", ".join(shortlist_pack["shortlist_paths"])
            )
        if skill_hints["must_view_agent"]:
            mandatory.append(
                "MUST view_file persona: " + ", ".join(skill_hints["must_view_agent"])
            )
        if mode == "plan":
            mandatory.append("A plan with zero search_web is INVALID.")
            mandatory.append("Emit ### Phase N sections for /ultradeep.")
            mandatory.append(
                "write_spec(slug, content, search_queries=[...]) — blocked without ≥5 queries for features."
            )
        if mode == "ultradeep":
            mandatory.append("Execute exactly ONE plan Phase this turn, then marathon_save_progress.")
            mandatory.append("Call marathon_search_gate before leaving research / before first code write.")
        if mode == "ask":
            mandatory.append("No application code edits.")
        if mode == "debug":
            mandatory.append("No fix before reproduce evidence + hypothesis.")
            mandatory.append("assert_phase to FIX is blocked until ≥3 search queries recorded.")

        next_tools: List[str] = []
        if mode in ("ask", "plan", "debug", "ultradeep"):
            next_tools.extend(["open_task", "skill_catalog", "record_skills_loaded"])
        if mode == "plan":
            next_tools.append("write_spec")
        if mode == "ultradeep":
            next_tools.extend(
                [
                    "marathon_load_progress or marathon_init",
                    "marathon_search_gate",
                    "marathon_save_progress",
                    "capture_shot",
                    "visual_critic",
                    "soak_run",
                    "set_ambition_ladder",
                ]
            )
        if mode == "verify":
            mandatory.append(
                "Run verify_bundle; soak_run; visual_critic; competitor_scan+compare_delta if feature; "
                "write_feedback; then request_claim_done."
            )
            next_tools.extend(
                [
                    "verify_bundle",
                    "soak_run",
                    "visual_critic",
                    "competitor_scan",
                    "compare_delta",
                    "write_feedback",
                    "evaluate_rubric",
                    "request_claim_done",
                ]
            )
        if mode == "debug":
            next_tools.extend(["blast_radius", "check_edit_safe", "record_tool_event", "verify_bundle"])

        return {
            "mode": mode,
            "goal": goal,
            "kind_suggestion": resolved_kind,
            "slug_suggestion": slug,
            "plan_phase": plan_phase,
            "mandatory_rules": mandatory,
            "suggested_next_tools": next_tools,
            "suggested_skills": {
                **skill_hints,
                "shortlist": shortlist_pack.get("shortlist") or [],
                "shortlist_paths": shortlist_pack.get("shortlist_paths") or [],
                "max_view_file": shortlist_pack.get("max_view_file") or 4,
                "how": shortlist_pack.get("rule")
                or "skill_catalog → pick ≤4 → view_file those only",
            },
            "constitution_excerpt": constitution_excerpt,
            "protocol_markdown": protocol,
            "instruction": (
                f"MODE ACTIVATED: /{mode}. Obey protocol_markdown exactly. "
                f"Goal: {goal or '(not set)'}. "
                + (
                    "Pick ≤4 from shortlist and view_file: "
                    + ", ".join(shortlist_pack.get("shortlist_paths") or [])
                    if shortlist_pack.get("shortlist_paths")
                    else "Call skill_catalog(query=goal), then view_file ≤4 picks."
                )
            ),
        }

    def _constitution_excerpt(self) -> str:
        text = self.get_constitution()
        # Keep activation payload smaller than full AGENTS when huge
        lines = text.strip().splitlines()
        if len(lines) <= 80:
            return text
        return "\n".join(lines[:80]) + "\n\n…(truncated; call get_constitution for full)…"
