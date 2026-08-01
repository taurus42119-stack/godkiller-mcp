"""
Game arena scorer (fail-closed) — separate from score_11.

  python -m benchmarks.score_game --arm 3_WITHOUT_MCP
  python -m benchmarks.score_game --arm 2_WITH_MCP
  python -m benchmarks.score_game --compare

Gates: build, boot, playable, fps (>=30 median), adaptive, pixel.
Human beauty is NOT scored here — open game/OPEN.md yourself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_ARENA = Path(
    os.environ.get(
        "GODKILLER_GAME_ARENA_ROOT",
        str(Path.home() / "Desktop" / "GODKILLER_GAME_ARENA"),
    )
)

ARMS = ("2_WITH_MCP", "3_WITHOUT_MCP")


def _load_gates(arena: Path) -> dict:
    path = arena / "hidden_oracle" / "gates.json"
    if not path.is_file():
        return {
            "fps_median_min": 60,
            "soak_seconds": 12,
            "boot_timeout_seconds": 90,
            "hang_kill_seconds": 180,
            "pixel_min_nonzero_ratio": 0.02,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _run(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> dict:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            shell=False,
        )
        def _dec(raw: bytes | None) -> str:
            if not raw:
                return ""
            return raw.decode("utf-8", errors="replace")

        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout_tail": _dec(p.stdout)[-2000:],
            "stderr_tail": _dec(p.stderr)[-2000:],
        }
    except subprocess.TimeoutExpired as e:
        def _dec(raw: bytes | str | None) -> str:
            if raw is None:
                return ""
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="replace")
            return raw

        return {
            "cmd": cmd,
            "returncode": -9,
            "error": f"timeout after {timeout}s",
            "stdout_tail": _dec(e.stdout)[-500:],
            "stderr_tail": _dec(e.stderr)[-500:],
        }


def _npm_cmd() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _node_cmd() -> str:
    return "node.exe" if os.name == "nt" else "node"


def _static_checks(game: Path) -> dict:
    src_files = list(game.joinpath("src").rglob("*.js")) + list(
        game.joinpath("src").rglob("*.ts")
    )
    blob = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in src_files)
    return {
        "has_three_import": bool(re.search(r"""from\s+['\"]three['\"]""", blob)),
        "has_gk_game": "__GK_GAME" in blob,
        "has_pointer_lock": "requestPointerLock" in blob,
        "has_adaptive": bool(
            re.search(r"adaptive|__GK_ADAPTIVE|pixelRatioCap|applyAdaptive", blob, re.I)
        ),
    }


def _ensure_tools(arena: Path, hang_kill: int) -> dict:
    tools = arena / "tools"
    if not (tools / "package.json").is_file():
        return {"ok": False, "error": "missing arena/tools/package.json"}
    marker = tools / "node_modules" / "playwright"
    installed = marker.is_dir()
    out: Dict[str, Any] = {"ok": False, "skipped_install": installed}
    if not installed:
        r = _run([_npm_cmd(), "install"], cwd=tools, timeout=hang_kill)
        out["npm_install"] = {"returncode": r.get("returncode"), "error": r.get("error")}
        if r.get("returncode") != 0:
            out["error"] = "npm install failed in arena/tools"
            return out
    # Chromium for soak (idempotent)
    br = _run(
        [_npx_cmd(), "playwright", "install", "chromium"],
        cwd=tools,
        timeout=hang_kill,
    )
    out["playwright_install"] = {
        "returncode": br.get("returncode"),
        "error": br.get("error"),
        "stderr_tail": br.get("stderr_tail"),
    }
    out["ok"] = br.get("returncode") == 0
    if not out["ok"]:
        out["error"] = "playwright install chromium failed"
    return out


def _npx_cmd() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def _kill_process_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _wait_http(url: str, timeout: float) -> bool:
    import urllib.request

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= getattr(resp, "status", 200) < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def score_arm(arena: Path, arm: str) -> Dict[str, Any]:
    gates = _load_gates(arena)
    game = arena / arm / "game"
    logs_arm = arena / "logs" / arm
    logs_arm.mkdir(parents=True, exist_ok=True)

    out: Dict[str, Any] = {
        "arm": arm,
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "game": str(game.resolve()) if game.exists() else None,
        "gates": gates,
        "dimensions": {},
        "hard_pass": False,
        "total": 0,
        "max_total": 6,
    }
    if not game.is_dir():
        out["error"] = f"missing game folder: {game}"
        return out

    static = _static_checks(game)
    out["static"] = static

    hang = int(gates.get("hang_kill_seconds", 180))
    npm = _npm_cmd()

    install = _run([npm, "install"], cwd=game, timeout=hang)
    out["npm_install"] = {"returncode": install.get("returncode"), "error": install.get("error")}
    build = _run([npm, "run", "build"], cwd=game, timeout=hang)
    build_ok = build.get("returncode") == 0
    out["npm_build"] = {
        "returncode": build.get("returncode"),
        "error": build.get("error"),
        "stderr_tail": build.get("stderr_tail"),
    }
    out["dimensions"]["build"] = 1.0 if build_ok else 0.0

    # Adaptive / playable static contributions (runtime can upgrade)
    out["dimensions"]["adaptive"] = 1.0 if static.get("has_adaptive") else 0.0
    out["dimensions"]["playable"] = (
        1.0 if static.get("has_gk_game") and static.get("has_pointer_lock") else 0.0
    )

    boot_ok = False
    fps_ok = False
    pixel_ok = False
    soak_data: Optional[dict] = None

    preview: Optional[subprocess.Popen] = None
    if build_ok:
        tools_install = _ensure_tools(arena, hang)
        out["tools_install"] = {
            "ok": tools_install.get("ok"),
            "error": tools_install.get("error"),
            "returncode": tools_install.get("returncode"),
        }
        preview_cmd = [npm, "run", "preview", "--", "--host", "127.0.0.1", "--port", "4173"]
        creationflags = 0
        preexec = None
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            preexec = os.setsid
        preview = subprocess.Popen(
            preview_cmd,
            cwd=str(game),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creationflags,
            preexec_fn=preexec,
        )
        url = "http://127.0.0.1:4173/"
        boot_timeout = float(gates.get("boot_timeout_seconds", 90))
        http_ok = _wait_http(url, min(boot_timeout, hang))
        out["preview_http"] = http_ok
        if http_ok and tools_install.get("ok"):
            soak_path = logs_arm / "soak_result.json"
            soak_seconds = int(gates.get("soak_seconds", 12))
            soak = _run(
                [
                    _node_cmd(),
                    str(arena / "tools" / "soak.mjs"),
                    url,
                    str(soak_seconds),
                    str(soak_path),
                ],
                cwd=arena / "tools",
                timeout=hang,
            )
            out["soak_proc"] = {
                "returncode": soak.get("returncode"),
                "error": soak.get("error"),
                "stderr_tail": soak.get("stderr_tail"),
            }
            if soak_path.is_file():
                soak_data = json.loads(soak_path.read_text(encoding="utf-8"))
                out["soak"] = soak_data
                boot_ok = bool(soak_data.get("boot"))
                if soak_data.get("stub_blocked"):
                    out["dimensions"]["playable"] = 0.0
                    out["stub_blocked"] = True
                elif soak_data.get("playable"):
                    out["dimensions"]["playable"] = 1.0
                fps = soak_data.get("fps_median")
                fps_min = float(gates.get("fps_median_min", 60))
                if isinstance(fps, (int, float)) and fps >= fps_min:
                    fps_ok = True
                    soft = float(gates.get("fps_soft_target", 60))
                    out["dimensions"]["fps"] = 1.0 if fps >= soft else 0.85
                else:
                    out["dimensions"]["fps"] = 0.0
                pix = soak_data.get("pixel_nonzero_ratio")
                pix_min = float(gates.get("pixel_min_nonzero_ratio", 0.02))
                if isinstance(pix, (int, float)) and pix >= pix_min:
                    pixel_ok = True
                    out["dimensions"]["pixel"] = 1.0
                else:
                    out["dimensions"]["pixel"] = 0.0
                if soak_data.get("adaptive_fired") or static.get("has_adaptive"):
                    out["dimensions"]["adaptive"] = 1.0
            else:
                out["dimensions"]["fps"] = 0.0
                out["dimensions"]["pixel"] = 0.0
                boot_ok = http_ok
        else:
            boot_ok = http_ok
            out["dimensions"]["fps"] = 0.0
            out["dimensions"]["pixel"] = 0.0
            if not tools_install.get("ok"):
                out["warning"] = "playwright tools install failed; fps/pixel gates fail-closed"

        _kill_process_tree(preview)
        preview = None
    else:
        out["dimensions"]["fps"] = 0.0
        out["dimensions"]["pixel"] = 0.0

    out["dimensions"]["boot"] = 1.0 if boot_ok else 0.0
    out["dimensions"].setdefault("fps", 0.0)
    out["dimensions"].setdefault("pixel", 0.0)

    # hard pass requires build+boot+fps+playable+adaptive+pixel
    hard = (
        out["dimensions"]["build"] >= 1.0
        and out["dimensions"]["boot"] >= 1.0
        and out["dimensions"]["playable"] >= 1.0
        and out["dimensions"]["fps"] >= 0.85
        and out["dimensions"]["adaptive"] >= 1.0
        and out["dimensions"]["pixel"] >= 1.0
    )
    out["hard_pass"] = hard
    out["total"] = round(sum(float(v) for v in out["dimensions"].values()), 3)
    out["human_layer"] = "Open game/OPEN.md (npm run preview) and judge beauty yourself."

    receipt = logs_arm / "score_game.json"
    receipt.write_text(json.dumps(out, indent=2), encoding="utf-8")
    out["receipt"] = str(receipt)
    return out


def compare(arena: Path) -> dict:
    rows = {}
    for arm in ARMS:
        path = arena / "logs" / arm / "score_game.json"
        if path.is_file():
            rows[arm] = json.loads(path.read_text(encoding="utf-8"))
    summary = {
        "compared_at": datetime.now(timezone.utc).isoformat(),
        "arms": {
            arm: {
                "hard_pass": rows.get(arm, {}).get("hard_pass"),
                "total": rows.get(arm, {}).get("total"),
                "dimensions": rows.get(arm, {}).get("dimensions"),
                "fps_median": (rows.get(arm, {}).get("soak") or {}).get("fps_median"),
            }
            for arm in ARMS
        },
        "note": "Beauty is human-only. Do not claim prettier from this JSON alone.",
    }
    out = arena / "logs" / "score_game_compare.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["receipt"] = str(out)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Score GODKILLER_GAME_ARENA arm")
    parser.add_argument("--arena-root", type=Path, default=DEFAULT_ARENA)
    parser.add_argument("--arm", choices=(*ARMS, "both"), default=None)
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()

    if args.compare and not args.arm:
        print(json.dumps(compare(args.arena_root), indent=2))
        return 0

    arms = ARMS if args.arm in (None, "both") else (args.arm,)
    if args.arm is None and not args.compare:
        parser.error("provide --arm or --compare")

    results = {a: score_arm(args.arena_root, a) for a in arms}
    payload: Dict[str, Any] = {"results": results}
    if args.compare or len(arms) == 2:
        payload["compare"] = compare(args.arena_root)
    print(json.dumps(payload, indent=2))
    # exit 0 always for tooling; hard_pass is in JSON
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
