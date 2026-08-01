"""Mint sealed process-dim evidence under an arena WITH arm (Proof-Kernel Next Slice D).

Usage (from package root):
  set GODKILLER_SEAL_KEY=<64 hex>
  set GODKILLER_ISOLATED_ARENA=%USERPROFILE%\\Desktop\\GODKILLER_ISOLATED_ARENA
  python scripts/mint_arm_process_dims.py
  python -m benchmarks.score_11 --arm 2_WITH_MCP
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from godkiller_mcp.evidence_integrity import attach_seal
from godkiller_mcp.evidence_store import EvidenceStore
from godkiller_mcp.schema import EvidenceType, Phase


def main() -> int:
    key = os.environ.get("GODKILLER_SEAL_KEY", "").strip()
    if not key:
        print("Set GODKILLER_SEAL_KEY (64 hex) first.", file=sys.stderr)
        return 2
    arena = Path(
        os.environ.get("GODKILLER_ISOLATED_ARENA")
        or (Path.home() / "Desktop" / "GODKILLER_ISOLATED_ARENA")
    )
    arm = arena / "2_WITH_MCP"
    if not arm.is_dir():
        print(f"Missing arm: {arm}", file=sys.stderr)
        return 2
    tasks = arm / ".godkiller" / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)

    store = EvidenceStore(persist_dir=tasks)
    secret = store._seal_key
    assert secret is not None
    state = store.open_task(kind="feature", goal="proof-kernel-next process dims mint")
    tid = state.handle.task_id

    MINT = {"provenance": "mint_fixture", "minted": True}

    store.submit_evidence(
        tid,
        EvidenceType.BLAST_RADIUS,
        "blast",
        {"server_authored": True, "symbol": "app", **MINT},
        server_authored=True,
    )
    store.submit_evidence(
        tid,
        EvidenceType.EDIT_SAFE,
        "edit",
        {"server_authored": True, "paths": ["app.py"], **MINT},
        server_authored=True,
    )
    store.submit_evidence(
        tid,
        EvidenceType.LOG,
        "exhaustive",
        {
            "server_authored": True,
            "engine": "exhaustive_reader_engine",
            "full_content": True,
            **MINT,
        },
        server_authored=True,
    )
    for src in (
        "verify_bundle",
        "exit_checklist",
        "council_finalize",
        "fault_probe",
        "visual_critic",
    ):
        payload = attach_seal(
            tid,
            {
                "source": src,
                "server_authored": True,
                "passed": True,
                **MINT,
                **(
                    {
                        "verdict": "GREEN",
                        "vision": {"passed": True, "expected_elements": ["OK"]},
                    }
                    if src == "visual_critic"
                    else {}
                ),
            },
            secret,
        )
        store.submit_evidence(tid, EvidenceType.LOG, src, payload, server_authored=True)

    store.update_metadata(
        tid,
        {
            "chosen_design": "A",
            "plan_os": True,
            "provenance": "mint_fixture",
            "minted": True,
        },
    )
    store.assert_phase(tid, Phase.REPRODUCE)
    store.mark_closed(tid)

    print(f"minted task_id={tid} provenance=mint_fixture")
    print("NOTE: score_11 excludes mint_fixture from earned dims 5-11")
    print(f"tasks_dir={tasks}")
    print(f"files={list(tasks.glob('*.json'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
