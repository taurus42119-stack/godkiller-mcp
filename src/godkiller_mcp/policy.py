"""Deterministic Policy Engine + process rubrics."""

from __future__ import annotations

import os
from typing import List, Optional, Sequence

from godkiller_mcp.schema import (
    EvidenceType,
    Phase,
    PolicyAction,
    RubricItem,
    RubricResult,
    TaskKind,
    TaskState,
)


BUGFIX_RUBRIC: List[RubricItem] = [
    RubricItem(
        id="reproduce_failing",
        description="Reproduce the bug with failing-test or exit-code evidence before fixing.",
        required_evidence_types=[EvidenceType.FAILING_TEST, EvidenceType.EXIT_CODE],
        required_phases=[Phase.REPRODUCE],
    ),
    RubricItem(
        id="hypothesis_balanced",
        description="At least one hypothesis with both supporting and refuting evidence refs.",
        min_hypotheses=1,
        require_support_and_refute=True,
        required_phases=[Phase.HYPOTHESIZE],
    ),
    RubricItem(
        id="localize",
        description="Localize failure with failing_slice or blast_radius evidence.",
        required_evidence_types=[EvidenceType.FAILING_SLICE, EvidenceType.BLAST_RADIUS],
        required_phases=[Phase.LOCALIZE],
    ),
    RubricItem(
        id="verify_pass",
        description="After fix, submit passing-test or exit-code 0 verification evidence.",
        required_evidence_types=[EvidenceType.PASSING_TEST, EvidenceType.EXIT_CODE],
        required_phases=[Phase.VERIFY],
    ),
    RubricItem(
        id="no_contradiction",
        description="No unresolved contradictory evidence remains.",
        block_on_contradiction=True,
    ),
]

FEATURE_RUBRIC: List[RubricItem] = [
    RubricItem(
        id="acceptance_defined",
        description="Feature goal recorded and phase advanced past open.",
        required_phases=[Phase.HYPOTHESIZE],
        min_hypotheses=1,
    ),
    RubricItem(
        id="ui_or_test_proof",
        description="UI journey/screenshot or passing tests prove the feature works.",
        required_evidence_types=[
            EvidenceType.UI_JOURNEY,
            EvidenceType.SCREENSHOT,
            EvidenceType.PASSING_TEST,
        ],
        required_phases=[Phase.VERIFY],
    ),
    RubricItem(
        id="no_contradiction",
        description="No unresolved contradictory evidence remains.",
        block_on_contradiction=True,
    ),
]

REFACTOR_RUBRIC: List[RubricItem] = [
    RubricItem(
        id="baseline_tests",
        description="Capture passing baseline tests before refactor.",
        required_evidence_types=[EvidenceType.PASSING_TEST],
        required_phases=[Phase.REPRODUCE],
    ),
    RubricItem(
        id="edit_safe",
        description="edit_safe / blast_radius check before large edits.",
        required_evidence_types=[EvidenceType.EDIT_SAFE, EvidenceType.BLAST_RADIUS],
        required_phases=[Phase.LOCALIZE],
    ),
    RubricItem(
        id="verify_pass",
        description="Tests still pass after refactor.",
        required_evidence_types=[EvidenceType.PASSING_TEST],
        required_phases=[Phase.VERIFY],
    ),
]


def rubric_for_kind(kind: TaskKind) -> List[RubricItem]:
    return {
        TaskKind.BUGFIX: BUGFIX_RUBRIC,
        TaskKind.FEATURE: FEATURE_RUBRIC,
        TaskKind.REFACTOR: REFACTOR_RUBRIC,
    }[kind]


class PolicyEngine:
    def __init__(
        self,
        max_consecutive_failures: int = 3,
        escalate_after_rejected_hypotheses: int = 3,
    ):
        self.max_consecutive_failures = max_consecutive_failures
        self.escalate_after_rejected_hypotheses = escalate_after_rejected_hypotheses

    def evaluate_rubric(self, state: TaskState) -> List[RubricResult]:
        results: List[RubricResult] = []
        for item in rubric_for_kind(state.handle.kind):
            results.append(self._eval_item(state, item))
        return results

    def _eval_item(self, state: TaskState, item: RubricItem) -> RubricResult:
        types = state.evidence_types()
        phases = set(state.phase_history)

        if item.block_on_contradiction:
            open_contradictions = [
                e for e in state.evidence if e.contradicts and e.type != EvidenceType.PASSING_TEST
            ]
            # Contradictions are unresolved if referenced evidence still present without override
            unresolved = []
            for e in open_contradictions:
                for cid in e.contradicts:
                    if state.evidence_by_id(cid):
                        unresolved.append(e.id)
            if unresolved:
                return RubricResult(
                    item_id=item.id,
                    passed=False,
                    reason=f"Unresolved contradictory evidence: {unresolved}",
                )
            return RubricResult(item_id=item.id, passed=True, reason="No contradictions.")

        if item.required_phases:
            if not any(p in phases for p in item.required_phases):
                return RubricResult(
                    item_id=item.id,
                    passed=False,
                    reason=f"Missing required phase(s): {[p.value for p in item.required_phases]}",
                )

        if item.min_hypotheses and len(state.hypotheses) < item.min_hypotheses:
            return RubricResult(
                item_id=item.id,
                passed=False,
                reason=f"Need >= {item.min_hypotheses} hypothesis; have {len(state.hypotheses)}",
            )

        if item.require_support_and_refute:
            ok = any(h.support_refs and h.refute_refs for h in state.hypotheses)
            if not ok:
                return RubricResult(
                    item_id=item.id,
                    passed=False,
                    reason="Hypothesis must include both support_refs and refute_refs.",
                )

        if item.required_evidence_types:
            # ANY of the listed types satisfies (OR semantics for alternatives)
            if not any(t in types for t in item.required_evidence_types):
                return RubricResult(
                    item_id=item.id,
                    passed=False,
                    reason=(
                        "Missing evidence type; need one of "
                        f"{[t.value for t in item.required_evidence_types]}"
                    ),
                )
            # Special-case verify: EXIT_CODE must be 0 when used for verify_pass
            if item.id == "verify_pass":
                if EvidenceType.PASSING_TEST in types:
                    return RubricResult(item_id=item.id, passed=True, reason="Passing test present.")
                exit_ok = any(
                    e.type == EvidenceType.EXIT_CODE and e.payload.get("exit_code") == 0
                    for e in state.evidence
                )
                if not exit_ok:
                    return RubricResult(
                        item_id=item.id,
                        passed=False,
                        reason="EXIT_CODE evidence must have exit_code=0 for verify.",
                    )

            # Special-case reproduce: failing test OR non-zero exit
            if item.id == "reproduce_failing":
                if EvidenceType.FAILING_TEST in types:
                    return RubricResult(item_id=item.id, passed=True, reason="Failing test present.")
                fail_exit = any(
                    e.type == EvidenceType.EXIT_CODE and e.payload.get("exit_code", 0) != 0
                    for e in state.evidence
                )
                if not fail_exit:
                    return RubricResult(
                        item_id=item.id,
                        passed=False,
                        reason="Need FAILING_TEST or non-zero EXIT_CODE for reproduce.",
                    )

        return RubricResult(item_id=item.id, passed=True, reason="OK")

    def all_passed(self, results: Sequence[RubricResult]) -> bool:
        return all(r.passed for r in results)

    def request_claim_done(
        self,
        state: TaskState,
        *,
        require_verify_bundle: bool = True,
        require_blast_radius: bool = True,
        handoff_feedback_ok: Optional[bool] = None,
        handoff_reason: str = "",
        require_quality_loop: bool = True,
        require_competitor_loop: bool = True,
        min_ambition_ladder: str = "L1_presence",
    ) -> tuple[bool, List[RubricResult], str]:
        from godkiller_mcp.verify_bundle import task_has_passing_verify_bundle

        # Soft-bypass only when explicitly relaxing for local experiments.
        if os.environ.get("GODKILLER_DEV_RELAX", "").strip() != "1":
            require_verify_bundle = True

        results = self.evaluate_rubric(state)
        if not self.all_passed(results):
            failed = [r for r in results if not r.passed]
            return False, results, "Rubric incomplete: " + "; ".join(
                f"{r.item_id}: {r.reason}" for r in failed
            )
        if Phase.VERIFY not in state.phase_history and state.handle.phase != Phase.VERIFY:
            return False, results, "Must reach VERIFY phase before claim_done."

        # Forced protocol: blast_radius before claiming edits landed safely
        if require_blast_radius and state.handle.kind in (
            TaskKind.BUGFIX,
            TaskKind.REFACTOR,
        ):
            if EvidenceType.BLAST_RADIUS not in state.evidence_types():
                return (
                    False,
                    results,
                    "Forced gate: blast_radius evidence required before claim_done "
                    "(call blast_radius before editing).",
                )

        # Ralph / 知乎: exit-code verify_bundle must pass
        if require_verify_bundle:
            ok_vb, reason_vb = task_has_passing_verify_bundle(state)
            if not ok_vb:
                return False, results, reason_vb

        # Hollow surface — unfinished / placeholder bodies cannot claim done
        from godkiller_mcp.hollow_surface import claim_hollow_gate

        ok_h, reason_h, _hollow = claim_hollow_gate(state)
        if not ok_h:
            return False, results, reason_h

        # Optional Planner/Builder/Eval soft gate (feedback.md)
        if handoff_feedback_ok is False:
            return (
                False,
                results,
                handoff_reason
                or "Forced handoff gate: write_feedback(passed=true) after eval.",
            )

        # Forced epistemics — all domains (game, SaaS, accounting, API)
        from godkiller_mcp.search_gates import claim_search_gate
        from godkiller_mcp.skill_gates import claim_skill_gate

        ok_s, reason_s = claim_search_gate(state)
        if not ok_s:
            return False, results, reason_s

        ok_sk, reason_sk = claim_skill_gate(state)
        if not ok_sk:
            return False, results, reason_sk

        # Feature dissatisfaction loop (competitors + ladder; visual when UI)
        from godkiller_mcp.quality_gates import quality_claim_gates

        ok_q, reason_q = quality_claim_gates(
            state,
            require_for_feature=require_quality_loop,
            require_competitor_loop=require_competitor_loop,
            min_ladder=min_ambition_ladder,
        )
        if not ok_q:
            return False, results, reason_q

        return True, results, "All rubric items + verify_bundle + search + quality gates satisfied."

    def decide(self, state: TaskState) -> PolicyAction:
        results = self.evaluate_rubric(state)
        rejected = sum(1 for h in state.hypotheses if h.status == "rejected")

        if state.failure_streak >= self.max_consecutive_failures:
            return PolicyAction.ESCALATE_FRONTIER
        if rejected >= self.escalate_after_rejected_hypotheses:
            return PolicyAction.ESCALATE_FRONTIER

        if self.all_passed(results) and state.handle.phase in (Phase.VERIFY, Phase.CLAIM_DONE):
            return PolicyAction.ALLOW_CLAIM_DONE

        # If stuck in FIX without verify evidence, replan
        if state.handle.phase == Phase.FIX and EvidenceType.PASSING_TEST not in state.evidence_types():
            if state.failure_streak >= 2:
                return PolicyAction.REPLAN

        if state.closed:
            return PolicyAction.STOP

        return PolicyAction.CONTINUE
