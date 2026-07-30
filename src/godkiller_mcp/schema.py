"""GODKILLER MCP Schema definitions using Pydantic BaseModel."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TaskKind(str, Enum):
    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"


class Phase(str, Enum):
    OPEN = "open"
    REPRODUCE = "reproduce"
    HYPOTHESIZE = "hypothesize"
    LOCALIZE = "localize"
    FIX = "fix"
    VERIFY = "verify"
    CLAIM_DONE = "claim_done"
    CLOSED = "closed"


class EvidenceType(str, Enum):
    FAILING_TEST = "failing_test"
    PASSING_TEST = "passing_test"
    EXIT_CODE = "exit_code"
    FAILING_SLICE = "failing_slice"
    BLAST_RADIUS = "blast_radius"
    SCREENSHOT = "screenshot"
    VISUAL_CRITIC = "visual_critic"
    SOAK_RUN = "soak_run"
    COMPETITOR_SCAN = "competitor_scan"
    COMPARE_DELTA = "compare_delta"
    UI_JOURNEY = "ui_journey"
    EDIT_SAFE = "edit_safe"
    HYPOTHESIS_SUPPORT = "hypothesis_support"
    HYPOTHESIS_REFUTE = "hypothesis_refute"
    LOG = "log"
    OTHER = "other"


class PolicyAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    REPLAN = "replan"
    CONTINUE = "continue"
    ESCALATE_FRONTIER = "escalate_frontier"


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    task_id: str = ""
    type: EvidenceType
    summary: str = ""
    description: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    uri: Optional[str] = None
    contradicts: List[str] = Field(default_factory=list)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    ref_ids: List[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    id: str = Field(default_factory=lambda: new_id("hyp"))
    statement: str = ""
    support_refs: List[str] = Field(default_factory=list)
    refute_refs: List[str] = Field(default_factory=list)
    status: str = "proposed"


class TaskHandle(BaseModel):
    task_id: str
    kind: TaskKind
    goal: str
    project_id: str = "default"
    phase: Phase = Phase.OPEN
    rubric_id: str = "bugfix_v1"
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TaskState(BaseModel):
    handle: TaskHandle
    current_phase: Phase = Phase.REPRODUCE
    closed: bool = False
    evidences: List[Evidence] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    phase_history: List[Phase] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def evidence(self) -> List[Evidence]:
        return self.evidences

    def evidence_types(self) -> List[EvidenceType]:
        return [e.type for e in self.evidences]


class RubricItem(BaseModel):
    id: str
    description: str
    required_evidence_types: List[EvidenceType] = Field(default_factory=list)
    required_phases: List[Phase] = Field(default_factory=list)
    any_of: bool = False
    min_hypotheses: int = 0
    require_support_and_refute: bool = False
    block_on_contradiction: bool = False


class RubricResult(BaseModel):
    item: Optional[RubricItem] = None
    item_id: Optional[str] = None
    passed: bool = True
    reason: str = ""
