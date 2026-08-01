"""Mode protocols served via MCP (activate_mode / get_protocol).

Loads the detailed Core-4 workflow markdown from .agents/workflows so any
project can get full ask/plan/debug/ultradeep intelligence without copying
.agents — as long as the model calls activate_mode first.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

MODES = ("ask", "plan", "debug", "ultradeep", "verify", "view")

MODE_TO_FILE = {
    "ask": "ask.md",
    "plan": "plan.md",
    "debug": "debug.md",
    "ultradeep": "ultradeep.md",
    "verify": "verify.md",
    "view": "view.md",
}

MODE_DEFAULT_KIND = {
    "ask": "feature",
    "plan": "feature",
    "debug": "bugfix",
    "ultradeep": "feature",
    "verify": "feature",
    "view": "feature",
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
        ("game", "phaser", "pixi", "godot", "gameplay", "fps", "webgl"),
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
        [
            ".agents/skills/security-and-hardening/SKILL.md",
            ".agents/skills/agent-ops/review-security/SKILL.md",
        ],
        None,
    ),
    (
        ("review", "code review", "pr review", "bugbot"),
        [
            ".agents/skills/agent-ops/review/SKILL.md",
            ".agents/skills/agent-ops/review-bugbot/SKILL.md",
            ".agents/skills/agent-ops/review-security/SKILL.md",
        ],
        None,
    ),
    (
        ("pr", "pull request", "ci fail", "merge conflict", "babysit"),
        [
            ".agents/skills/agent-ops/babysit/SKILL.md",
            ".agents/skills/agent-ops/split-to-prs/SKILL.md",
        ],
        None,
    ),
    (
        ("automate", "cron", "loop task", "scheduled"),
        [
            ".agents/skills/agent-ops/automate/SKILL.md",
            ".agents/skills/agent-ops/loop/SKILL.md",
        ],
        None,
    ),
    (
        ("create skill", "write skill", "skill.md", "agent skill"),
        [
            ".agents/skills/agent-ops/create-skill/SKILL.md",
            ".agents/skills/agent-ops/create-rule/SKILL.md",
            ".agents/skills/agent-ops/create-hook/SKILL.md",
        ],
        None,
    ),
    (
        ("shell", "powershell", "bash script", "terminal command"),
        [".agents/skills/agent-ops/shell/SKILL.md"],
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
        bundled_dir = Path(__file__).resolve().parent / "protocols"
        for mode in MODES:
            path = self.workflows_dir / MODE_TO_FILE[mode]
            bundled = bundled_dir / MODE_TO_FILE[mode]
            available = path.exists() or bundled.exists()
            out.append(
                {
                    "mode": mode,
                    "available": available,
                    "path": str(path if path.exists() else bundled),
                    "default_kind": MODE_DEFAULT_KIND[mode],
                }
            )
        return out

    def get_protocol(self, mode: str) -> str:
        mode = mode.lower().strip().lstrip("/")
        if mode not in MODE_TO_FILE:
            raise ValueError(f"Unknown mode '{mode}'. Use one of: {', '.join(MODES)}")
        path = self.workflows_dir / MODE_TO_FILE[mode]
        if path.exists():
            return path.read_text(encoding="utf-8")
        # Bundled fallback (package ships protocols/ so MCP works without copying .agents)
        bundled = Path(__file__).resolve().parent / "protocols" / MODE_TO_FILE[mode]
        if bundled.exists():
            return bundled.read_text(encoding="utf-8")
        raise FileNotFoundError(f"Protocol file missing: {path} (and no bundled {bundled.name})")

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
        include_protocol: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        from godkiller_mcp.compact_io import protocol_preview, verbose_enabled

        mode = mode.lower().strip().lstrip("/")
        protocol = self.get_protocol(mode)
        fat = verbose_enabled(verbose) or include_protocol
        resolved_kind = kind or MODE_DEFAULT_KIND.get(mode, "feature")
        skill_hints = suggest_skills_for_goal(goal)

        try:
            from godkiller_mcp.skill_catalog import (
                build_catalog,
                resolve_skill_roots,
                suggest_from_catalog,
            )

            catalog = build_catalog(resolve_skill_roots(self.agents_root))
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
            "Gates on disk beat chat. Search before invent. No placeholder-as-done.",
            "claim_done needs verify_bundle (plus UI visual_step sequence when UI).",
            "Edits: blast_radius then check_edit_safe. Skills: skill_catalog then <=4 view_file.",
            "Follow protocol_preview / get_protocol(mode). Prefer compact tool results.",
        ]
        if shortlist_pack.get("shortlist_paths"):
            mandatory.append(
                "Shortlist <=4: " + ", ".join(shortlist_pack["shortlist_paths"])
            )
        if mode == "plan":
            mandatory.extend(
                [
                    ">=5 search_web; ### Phase N — Title (not bare module H3s).",
                    "UI plans: Phase playtest->capture->inspect->recheck; plan_validate.",
                ]
            )
        if mode == "ultradeep":
            mandatory.extend(
                [
                    "ONE Phase this turn + marathon_save. plan_refute HOLD before edit_safe.",
                    "Per-file: think->plan->edit_safe(one file)->verify->advance. No batch rush.",
                    "Use needed tools only — not every MCP every turn.",
                ]
            )
        if mode == "view":
            mandatory.extend(
                [
                    "NOT view_file alone. view_start->search->attack->draft->refute->finalize.",
                    "No app code edits. Weaknesses-only; praise without HOLD = fail.",
                ]
            )
        if mode == "ask":
            mandatory.append("No application code edits. Handoff to /plan.")
        if mode == "debug":
            mandatory.extend(
                [
                    "No fix before reproduce + hypothesis. >=3 searches before FIX.",
                    "self_ctf on THIS workspace only when armed.",
                ]
            )
        if mode == "verify":
            mandatory.append("Empirical proof + claim_done gates only.")
        if mode in ("ask", "plan", "debug", "ultradeep", "verify", "view"):
            mandatory.append(
                "If <99% sure: view_propose_study (exemplar repos) — no silent invention."
            )

        next_tools: List[str] = []
        if mode in ("ask", "plan", "debug", "ultradeep", "view"):
            next_tools.extend(["skill_catalog", "record_skills_loaded"])
        if mode == "ask":
            next_tools.extend(["open_task", "submit_evidence"])
        if mode == "plan":
            next_tools.extend(
                ["write_spec", "gk_meta.plan_validate", "submit_evidence", "competitor_scan"]
            )
        if mode == "view":
            next_tools.extend(
                [
                    "view_propose_study",
                    "view_start",
                    "view_search",
                    "view_attack",
                    "view_draft",
                    "view_refute",
                    "view_finalize",
                ]
            )
        if mode == "ultradeep":
            next_tools.extend(
                [
                    "ultradeep_plan_refute",
                    "marathon_search_gate",
                    "ultradeep_queue_files",
                    "ultradeep_think_file",
                    "check_edit_safe",
                    "verify_bundle",
                    "marathon_save_progress",
                ]
            )
        if mode == "debug":
            next_tools.extend(
                [
                    "open_task",
                    "assert_phase",
                    "submit_evidence",
                    "debug_self_ctf_start",
                    "blast_radius",
                    "check_edit_safe",
                    "verify_bundle",
                ]
            )
        if mode == "verify":
            next_tools.extend(
                [
                    "verify_bundle",
                    "fault_probe",
                    "exit_checklist",
                    "visual_critic",
                    "request_claim_done",
                ]
            )

        shortlist_thin = [
            {"path": s.get("path"), "name": s.get("name")}
            for s in (shortlist_pack.get("shortlist") or [])
            if isinstance(s, dict)
        ][:4]

        out: Dict[str, Any] = {
            "mode": mode,
            "goal": goal,
            "kind_suggestion": resolved_kind,
            "slug_suggestion": slug,
            "plan_phase": plan_phase,
            "mandatory_rules": mandatory,
            "suggested_next_tools": next_tools,
            "suggested_skills": {
                "shortlist_paths": shortlist_pack.get("shortlist_paths") or [],
                "shortlist": shortlist_thin if not fat else (shortlist_pack.get("shortlist") or []),
                "max_view_file": shortlist_pack.get("max_view_file") or 4,
                "must_view_agent": skill_hints.get("must_view_agent") or [],
            },
            "agents_md_path": str(self.agents_md) if self.agents_md.exists() else None,
            "protocol_preview": protocol_preview(protocol),
            "protocol_chars": len(protocol),
            "compact": not fat,
            "token_hint": (
                "Compact activate (default). Full protocol: get_protocol or "
                "activate include_protocol=true. Verbose status: gk_meta.status detail=true. "
                "Pretty JSON: GODKILLER_JSON_PRETTY=1."
            ),
            "instruction": (
                f"MODE /{mode} on. Obey protocol_preview (or get_protocol). "
                f"Goal: {goal or '(not set)'}."
            ),
        }
        if fat:
            out["constitution_excerpt"] = self._constitution_excerpt()
            out["protocol_markdown"] = protocol
        else:
            out["protocol_markdown_omitted"] = True
            out["constitution_excerpt_omitted"] = True
        return out

    def _constitution_excerpt(self) -> str:
        text = self.get_constitution()
        lines = text.strip().splitlines()
        if len(lines) <= 40:
            return text
        return "\n".join(lines[:40]) + "\n\n…(truncated; read agents_md_path on disk)…"

