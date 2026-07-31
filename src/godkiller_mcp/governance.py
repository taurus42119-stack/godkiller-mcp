"""Governance-lite — privileged tool discipline + plan lock (GODKILLER-native)."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, Optional, Set


# Tools that mutate truth / close work — need task context in STRICT mode.
PRIVILEGED_TOOLS: Set[str] = {
    "request_claim_done",
    "verify_bundle",
    "fault_probe",
    "check_edit_safe",
    "blast_radius",
    "assert_phase",
    "submit_evidence",
    "hollow_surface",
    "gk_plan_validate",
    "ultradeep_advance_file",
    "ultradeep_plan_refute",
    "ultradeep_repair_wake",
    "view_start",
    "view_record_search",
    "view_record_attack",
    "view_draft_plan",
    "view_refute_plan",
    "view_finalize",
    "write_guard",
    "write_guard_set_paths",
    "swarm_spawn",
    "swarm_submit",
    "swarm_collect",
    "debug_self_ctf_start",
    "debug_self_ctf_tick",
    "debug_self_ctf_run_until",
    "tool_propose",
    "tool_approve",
    "tool_reject_all",
    "tool_used",
}


def strict_mode() -> bool:
    return os.environ.get("GODKILLER_STRICT", "").strip() in ("1", "true", "yes", "on")


def plan_always_required() -> bool:
    """Write-through-plan: default ON. GODKILLER_PLAN_LOCK=0 only under DEV_RELAX."""
    from godkiller_mcp.ship_mode import env_disables, relax_enabled

    if env_disables("GODKILLER_PLAN_LOCK"):
        return False
    if os.environ.get("GODKILLER_PLAN_LOCK", "1").strip() in ("0", "false", "off"):
        # Ship mode ignores the kill-switch
        if not relax_enabled():
            return True
        return False
    return True


def plan_digest(plan: Any) -> str:
    material = json.dumps(plan, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def require_task_for_privileged(tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
    if not strict_mode():
        return None
    if tool_name not in PRIVILEGED_TOOLS:
        return None
    if arguments.get("task_id"):
        return None
    return (
        f"GODKILLER_STRICT: privileged tool '{tool_name}' requires task_id "
        "(open_task first)."
    )


def require_valid_plan(state) -> tuple[bool, str]:
    if not plan_always_required():
        return True, "plan_lock off"
    from godkiller_mcp.ship_mode import relax_enabled

    if relax_enabled():
        return True, "plan_lock skipped (DEV_RELAX)"
    meta = (state.handle.metadata or {}).get("plan_validation") or {}
    if meta.get("valid"):
        digest = (state.handle.metadata or {}).get("plan_digest") or meta.get("digest")
        return True, f"plan_lock ok digest={digest or 'n/a'}"
    return (
        False,
        "Forced gate: write-through-plan — call gk_meta.plan_validate with full 9-step plan "
        "before claim_done / edit_safe.",
    )
