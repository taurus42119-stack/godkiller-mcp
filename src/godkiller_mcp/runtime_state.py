"""Shared runtime objects for facades/handlers — not under site-packages.

Handlers import from here instead of ``dispatch`` to avoid circular peel.
``dispatch`` re-exports these names for backward compatibility.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from mcp.types import TextContent

from godkiller_mcp.browser_bridge import BrowserEvidenceBridge
from godkiller_mcp.browser_runtime import PlaywrightBrowser
from godkiller_mcp.epistemic_router import EpistemicRouter
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.handoff_docs import SpecFeedbackStore
from godkiller_mcp.loop_guard import LoopDetector
from godkiller_mcp.marathon import MarathonRelay
from godkiller_mcp.memory_lessons import LessonMemory
from godkiller_mcp.modes import ModeProtocolStore
from godkiller_mcp.plan_os import PlanOS
from godkiller_mcp.policy import PolicyEngine
from godkiller_mcp.runtime_paths import (
    handoff_dir,
    lessons_db_path,
    marathon_dir,
    package_root,
    resolve_state_root,
    tasks_dir,
    ui_artifacts_dir,
)
from godkiller_mcp.secrets_loader import ScopeSafeSecretsLoader
from godkiller_mcp.verify_bundle import VerifyBundleRunner
from godkiller_mcp.vision_bridge import VisionBridge
from godkiller_mcp.workflow_graph import WorkflowGraph

# Mutable state lives under GODKILLER_HOME / workspace /.godkiller — never site-packages.
STATE_ROOT = resolve_state_root()
STORE_DIR = tasks_dir(STATE_ROOT)
MARATHON_DIR = marathon_dir(STATE_ROOT)
HANDOFF_DIR = handoff_dir(STATE_ROOT)
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
