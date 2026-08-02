"""VIEW propose-study — when confidence < 99%, propose reference-repo lookalikes immediately.

Does not edit application code. Agent must show the proposal to the user / chat.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

# Anything below this → propose VIEW study NOW (user policy: not 99% sure ⇒ propose)
CONFIDENCE_PROPOSE_BELOW = 99.0


def should_propose_view(confidence_pct: Optional[float]) -> bool:
    if confidence_pct is None:
        return True
    try:
        return float(confidence_pct) < CONFIDENCE_PROPOSE_BELOW
    except (TypeError, ValueError):
        return True


def build_view_study_proposal(
    *,
    goal: str,
    confidence_pct: Optional[float] = None,
    topics: Optional[Sequence[str]] = None,
    known_gaps: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Structured plan: look at / copy-study exemplar files from public repos (read-only)."""
    conf = None if confidence_pct is None else float(confidence_pct)
    propose = should_propose_view(conf)
    topic_list = [str(t).strip() for t in (topics or []) if str(t).strip()]
    gaps = [str(g).strip() for g in (known_gaps or []) if str(g).strip()]
    if not topic_list:
        topic_list = [
            "reference implementation in a public repo",
            "API / file layout that already solves a similar problem",
            "tests or fixtures that show expected behavior",
        ]

    steps = [
        {
            "step": 1,
            "action": "name_gap",
            "detail": "State what you are <99% sure about (API, pattern, file shape, dependency).",
        },
        {
            "step": 2,
            "action": "hunt_exemplars",
            "detail": (
                "Search public repos / docs for similar work (github, official samples). "
                "Prefer well-known projects over random gists."
            ),
        },
        {
            "step": 3,
            "action": "propose_to_user",
            "detail": (
                "IMMEDIATELY propose in chat: which repos/paths to open, which files to deep-read "
                "(copy-study — read & learn layout; do not paste wholesale as done work)."
            ),
        },
        {
            "step": 4,
            "action": "deep_read",
            "detail": (
                "Exhaustive read of chosen exemplar files (godkiller_exhaustive_read / view_file). "
                "Cite paths + what you will adapt."
            ),
        },
        {
            "step": 5,
            "action": "optional_full_view",
            "detail": (
                "If research plan must be sealed: activate_mode(view) → view_start → … → view_finalize."
            ),
        },
    ]

    chat_template = (
        "### VIEW study proposal (confidence {conf}% < 99%)\n"
        "Goal: {goal}\n"
        "I am not ≥99% sure about: {gaps}\n"
        "I propose we look at exemplar work in public repos / samples for:\n"
        "{topics}\n"
        "Next: I will list concrete repo+file paths to deep-read (copy-study only, no blind paste)."
    ).format(
        conf="?" if conf is None else f"{conf:.1f}",
        goal=goal.strip() or "(unspecified)",
        gaps="; ".join(gaps) if gaps else "(state the uncertainty)",
        topics="\n".join(f"- {t}" for t in topic_list),
    )

    return {
        "ok": True,
        "propose_now": propose,
        "confidence_pct": conf,
        "threshold_pct": CONFIDENCE_PROPOSE_BELOW,
        "rule": "If confidence < 99%, propose VIEW/example-hunt IMMEDIATELY — do not silently guess.",
        "goal": goal.strip(),
        "topics": topic_list,
        "known_gaps": gaps,
        "steps": steps,
        "chat_template": chat_template,
        "next_tools": [
            "gk_mode.activate(mode=view)",
            "gk_mode.view_propose_study",
            "gk_mode.view_start",
            "gk_code.search / godkiller_hyper_search",
            "godkiller_exhaustive_read / view_file on exemplar paths",
            "competitor_scan",
        ],
        "forbidden": [
            "Claiming done from memory without exemplar evidence",
            "Blind copy-paste of entire foreign repos as the deliverable",
            "Skipping the user-facing proposal when confidence < 99%",
        ],
    }
