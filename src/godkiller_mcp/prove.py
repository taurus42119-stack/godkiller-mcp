"""
Host-side prove — re-run verification OUTSIDE the agent's self-report.

Why this exists (Antigravity confusion):
  MCP tools only run when the agent *calls* GODKILLER.
  The IDE still has native Write/Edit/terminal that bypass MCP entirely.
  So kernel gates cannot see those edits unless:
    (1) the host installs a PreToolUse hook, or
    (2) a human/CI runs this prove script against the tree before trusting "done".

  python -m godkiller_mcp.prove --workspace .
  python -m godkiller_mcp.prove --workspace . --targets app.py --fail-on-survivors
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from godkiller_mcp.fault_probe import run_fault_probe
from godkiller_mcp.freshness import material_hash
from godkiller_mcp.hollow_surface import scan_hollow_surface
from godkiller_mcp.verify_bundle import VerifyBundleRunner


def prove(
    workspace: str | Path,
    *,
    targets: Optional[List[str]] = None,
    test_command: str = "python -m pytest -q --tb=no",
    fail_on_survivors: bool = True,
    fail_on_hollow: bool = True,
) -> Dict[str, Any]:
    ws = Path(workspace).resolve()
    report: Dict[str, Any] = {
        "ok": True,
        "workspace": str(ws),
        "gates": {},
        "reasons": [],
    }

    # 1) Real verify (server-side runner, not agent transcript)
    vr = VerifyBundleRunner(timeout_sec=120).run(ws, [test_command])
    vpay = vr.to_payload()
    paths = targets or [str(ws)]
    mat = material_hash(paths, workspace=ws)
    vpay["material_hash"] = mat["material_hash"]
    vpay["material_files"] = mat["files"]
    report["gates"]["verify_bundle"] = {
        "passed": vr.passed,
        "result_digest": vpay.get("result_digest"),
        "material_hash": mat["material_hash"],
        "summary": vr.summary,
    }
    if not vr.passed:
        report["ok"] = False
        report["reasons"].append(vr.summary)

    # 2) Hollow surface on targets / workspace top-level py
    hollow_roots = targets or list(str(p) for p in ws.glob("*.py"))
    if hollow_roots and fail_on_hollow:
        hr = scan_hollow_surface(hollow_roots)
        report["gates"]["hollow_surface"] = hr.to_payload()
        if not hr.clean:
            report["ok"] = False
            report["reasons"].append(hr.to_payload()["summary"])

    # 3) Diff-scoped / explicit fault probe
    if fail_on_survivors:
        fr = run_fault_probe(
            workspace=ws,
            targets=targets,
            test_command=test_command,
            timeout_sec=90,
            max_mutants=10,
        )
        report["gates"]["fault_probe"] = fr.to_payload()
        if not fr.clean and "SKIP" not in (fr.summary or ""):
            report["ok"] = False
            report["reasons"].append(fr.summary)
        elif fr.skipped_reason and "no python targets" in fr.skipped_reason and targets:
            report["ok"] = False
            report["reasons"].append(fr.skipped_reason)

    report["verdict"] = "PROVED" if report["ok"] else "NOT_PROVED"
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="GODKILLER host prove — fail-closed re-verification outside the agent"
    )
    parser.add_argument("--workspace", default=".", help="Project root")
    parser.add_argument(
        "--targets",
        nargs="*",
        default=None,
        help="Python files to hollow/probe (default: git diff scope)",
    )
    parser.add_argument(
        "--test-command",
        default="python -m pytest -q --tb=no",
        help="Verify command (allowlisted shapes only inside MCP; here free-form for host)",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip fault_probe",
    )
    parser.add_argument(
        "--no-hollow",
        action="store_true",
        help="Skip hollow_surface",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON")
    args = parser.parse_args(argv)

    # Host prove may use richer test commands than MCP allowlist — runner still executes safely.
    result = prove(
        args.workspace,
        targets=args.targets,
        test_command=args.test_command,
        fail_on_survivors=not args.no_probe,
        fail_on_hollow=not args.no_hollow,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"verdict: {result['verdict']}")
        for r in result.get("reasons") or []:
            print(f"  - {r}")
        vb = result["gates"].get("verify_bundle") or {}
        print(f"  verify: passed={vb.get('passed')} material={str(vb.get('material_hash', ''))[:16]}…")
        fp = result["gates"].get("fault_probe") or {}
        if fp:
            print(f"  probe: {fp.get('summary')}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
