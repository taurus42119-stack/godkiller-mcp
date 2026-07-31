"""Application context for GODKILLER MCP (testable wiring)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class AppContext:
    state_root: Path
    store: EvidenceStore
    policy: PolicyEngine
    browser: BrowserEvidenceBridge
    lessons: LessonMemory
    marathon: MarathonRelay
    modes: ModeProtocolStore
    verify_runner: VerifyBundleRunner
    loops: LoopDetector
    handoff: SpecFeedbackStore
    secrets: ScopeSafeSecretsLoader
    router: EpistemicRouter
    vision: VisionBridge
    plan_os: PlanOS
    workflow: WorkflowGraph
    pw_browser: PlaywrightBrowser
    package_root: Path


def build_app_context(workspace: str | Path | None = None) -> AppContext:
    state_root = resolve_state_root(workspace)
    store = EvidenceStore(persist_dir=tasks_dir(state_root))
    agents = Path.cwd() / ".agents"
    if not agents.exists():
        agents = package_root() / ".agents"
    return AppContext(
        state_root=state_root,
        store=store,
        policy=PolicyEngine(),
        browser=BrowserEvidenceBridge(store, artifact_dir=ui_artifacts_dir(state_root)),
        lessons=LessonMemory(str(lessons_db_path(state_root))),
        marathon=MarathonRelay(marathon_dir(state_root)),
        modes=ModeProtocolStore(agents),
        verify_runner=VerifyBundleRunner(),
        loops=LoopDetector(),
        handoff=SpecFeedbackStore(handoff_dir(state_root)),
        secrets=ScopeSafeSecretsLoader(Path.cwd() / ".env"),
        router=EpistemicRouter(),
        vision=VisionBridge(),
        plan_os=PlanOS(),
        workflow=WorkflowGraph(store),
        pw_browser=PlaywrightBrowser(artifact_dir=ui_artifacts_dir(state_root)),
        package_root=package_root(),
    )
