"""Browser evidence bridge — register UI journeys/screenshots into Evidence Graph.

For real browser control use `godkiller_mcp.browser_runtime.PlaywrightBrowser`
(exposed via `gk_browser` actions: navigate/snapshot/screenshot/click/fill).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import Evidence, EvidenceType


@dataclass
class JourneyStep:
    action: str
    target: str = ""
    expect: str = ""
    screenshot_uri: Optional[str] = None


@dataclass
class JourneyResult:
    name: str
    passed: bool
    steps: List[JourneyStep] = field(default_factory=list)
    screenshot_uris: List[str] = field(default_factory=list)
    notes: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "notes": self.notes,
            "steps": [s.__dict__ for s in self.steps],
            "screenshot_uris": self.screenshot_uris,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }


class BrowserEvidenceBridge:
    """Converts browser/UI artifacts into Evidence nodes for Policy gating."""

    def __init__(self, store: EvidenceStore, artifact_dir: Optional[str | Path] = None):
        self.store = store
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path("arena/results/ui_artifacts")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def register_screenshot(
        self,
        task_id: str,
        path: str,
        summary: str = "UI screenshot evidence",
        *,
        step_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Evidence:
        p = Path(path)
        extra: Dict[str, Any] = {}
        if step_id:
            extra["step_id"] = str(step_id).strip()
        if source:
            extra["source"] = str(source).strip()
        if not p.exists():
            # Still record intent but mark missing
            return self.store.submit_evidence(
                task_id=task_id,
                evidence_type=EvidenceType.SCREENSHOT,
                summary=f"{summary} (MISSING FILE: {path})",
                payload={"exists": False, "path": path, **extra},
                uri=path,
            )
        return self.store.submit_evidence(
            task_id=task_id,
            evidence_type=EvidenceType.SCREENSHOT,
            summary=summary,
            payload={
                "exists": True,
                "size": p.stat().st_size,
                "path": str(p.resolve()),
                **extra,
            },
            uri=str(p.resolve()),
        )

    def register_journey(
        self,
        task_id: str,
        journey: JourneyResult,
    ) -> Evidence:
        # Persist journey JSON artifact
        from godkiller_mcp.path_sandbox import normalize_artifact_name

        safe_name = normalize_artifact_name(journey.name.replace(" ", "_"))
        out = (self.artifact_dir / f"{task_id}_{safe_name}.json").resolve()
        out.relative_to(Path(self.artifact_dir).resolve())
        out.write_text(json.dumps(journey.to_payload(), indent=2), encoding="utf-8")

        # Register screenshots referenced by journey
        for uri in journey.screenshot_uris:
            if uri:
                self.register_screenshot(task_id, uri, summary=f"Journey screenshot: {journey.name}")

        return self.store.submit_evidence(
            task_id=task_id,
            evidence_type=EvidenceType.UI_JOURNEY,
            summary=f"UI journey '{journey.name}' passed={journey.passed}",
            payload=journey.to_payload(),
            uri=str(out.resolve()),
        )

    def require_ui_proof_for_feature(self, task_id: str) -> tuple[bool, str]:
        from godkiller_mcp.search_gates import needs_visual_loop
        from godkiller_mcp.visual_sequence_gate import visual_sequence_claim_gate

        state = self.store.get(task_id)
        if not needs_visual_loop(state):
            return True, "UI proof not required (backend/API surface or require_visual=false)."
        journeys = [e for e in state.evidence if e.type == EvidenceType.UI_JOURNEY]
        if journeys and not any((e.payload or {}).get("passed") for e in journeys):
            # Failed journeys alone do not satisfy proof — sequence gate still applies
            pass
        return visual_sequence_claim_gate(state)
