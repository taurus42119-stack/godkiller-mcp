"""Evidence integrity seal — disk JSON forgeries must not unlock armor gates.

Prefer host env `GODKILLER_SEAL_KEY` (agent cannot casually rewrite workspace secrets).
Legacy persist_dir/.seal_key is read-only when GODKILLER_ALLOW_LEGACY_SEAL=1 (never ship).
Default: never auto-mint .seal_key — see docs/SEAL_KEY.md.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Set

ARMOR_SOURCES: Set[str] = {
    "verify_bundle",
    "fault_probe",
    "hollow_surface",
    "visual_critic",
    "soak_run",
    "competitor_scan",
    "compare_delta",
    "council_finalize",
    "exit_checklist",
    "swarm_collect",
    "write_guard",
    "ultradeep_plan_refute",
    "ultradeep_repair_wake",
    "view_finalize",
    "tool_propose",
    "tool_approve",
    "tool_used",
}


def _seal_path(persist_dir: Path) -> Path:
    return Path(persist_dir) / ".seal_key"


def _decode_env_key(raw: str) -> bytes:
    s = raw.strip()
    if not s:
        raise ValueError("empty GODKILLER_SEAL_KEY")
    # Hex (64 chars = 32 bytes) preferred
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        return bytes.fromhex(s)
    # Raw utf-8 passphrase → derive 32 bytes (stable)
    return hashlib.sha256(s.encode("utf-8")).digest()


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _is_ship_profile() -> bool:
    try:
        from godkiller_mcp.ship_mode import profile

        return profile() == "ship"
    except ImportError:
        raise
    except Exception as exc:
        if os.environ.get("GODKILLER_PROFILE", "").strip().lower() in (
            "ship",
            "prod",
            "production",
            "strict",
        ):
            return True
        raise RuntimeError(f"seal profile check failed: {exc}") from exc


def seal_key_source() -> str:
    if os.environ.get("GODKILLER_SEAL_KEY", "").strip():
        return "env"
    if _truthy_env("GODKILLER_SEAL_REQUIRE_ENV") or _is_ship_profile():
        return "require_env"
    if _truthy_env("GODKILLER_ALLOW_LEGACY_SEAL"):
        return "legacy_allowed"
    return "env_required"


_warned_legacy = False


def load_or_create_seal_key(persist_dir: Path) -> bytes:
    """
    Priority:
      1) GODKILLER_SEAL_KEY env (host-only) — never written to workspace
      2) existing persist_dir/.seal_key ONLY if GODKILLER_ALLOW_LEGACY_SEAL=1 and not ship
      3) never auto-mint — raise (see docs/SEAL_KEY.md)
    """
    global _warned_legacy
    env_raw = os.environ.get("GODKILLER_SEAL_KEY", "").strip()
    require_env = _truthy_env("GODKILLER_SEAL_REQUIRE_ENV")
    ship = _is_ship_profile()
    if ship and not env_raw:
        require_env = True
    allow_legacy = _truthy_env("GODKILLER_ALLOW_LEGACY_SEAL") and not ship
    path = _seal_path(persist_dir)

    if env_raw:
        key = _decode_env_key(env_raw)
        # Host wins: do not trust/update workspace file as authority
        marker = Path(persist_dir) / ".seal_key_SOURCE"
        try:
            persist_dir.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                "source=GODKILLER_SEAL_KEY (env)\n"
                "workspace .seal_key is ignored while env is set\n"
                "see docs/SEAL_KEY.md\n",
                encoding="utf-8",
            )
        except OSError:
            pass
        return key

    if require_env or ship:
        raise RuntimeError(
            "GODKILLER_SEAL_KEY is unset under ship/require-env posture — "
            "set a host env secret (see docs/SEAL_KEY.md). "
            "Workspace .seal_key is not used in ship mode."
        )

    if allow_legacy and path.exists():
        if not _warned_legacy and not _truthy_env("GODKILLER_SEAL_QUIET"):
            warnings.warn(
                "Using legacy persist_dir/.seal_key via GODKILLER_ALLOW_LEGACY_SEAL=1 — "
                "migrate to GODKILLER_SEAL_KEY env (docs/SEAL_KEY.md).",
                UserWarning,
                stacklevel=2,
            )
            _warned_legacy = True
        return path.read_bytes().strip()

    if path.exists() and not allow_legacy:
        raise RuntimeError(
            "Found persist_dir/.seal_key but auto-mint/legacy read is disabled. "
            "Set GODKILLER_SEAL_KEY (preferred) or GODKILLER_ALLOW_LEGACY_SEAL=1 "
            "for off-ship compat only — see docs/SEAL_KEY.md"
        )

    raise RuntimeError(
        "GODKILLER_SEAL_KEY is unset and workspace .seal_key will not be auto-created. "
        "Export GODKILLER_SEAL_KEY=<64 hex chars> (see docs/SEAL_KEY.md). "
        "Off-ship only: GODKILLER_ALLOW_LEGACY_SEAL=1 to read an existing .seal_key."
    )


def seal_status(persist_dir: Path) -> Dict[str, Any]:
    """Introspection for demos / scorecard (no secret material)."""
    src = seal_key_source()
    path = _seal_path(persist_dir)
    env_set = bool(os.environ.get("GODKILLER_SEAL_KEY", "").strip())
    if src == "require_env" and not env_set:
        display = "require_env_missing"
    elif src == "env_required" and not env_set:
        display = "env_required"
    else:
        display = src
    return {
        "source": display,
        "env_set": env_set,
        "require_env": _truthy_env("GODKILLER_SEAL_REQUIRE_ENV"),
        "allow_legacy_seal": _truthy_env("GODKILLER_ALLOW_LEGACY_SEAL"),
        "legacy_file_present": path.exists(),
        "hint": (
            "Host env key active — workspace .seal_key ignored"
            if src == "env"
            else "Set GODKILLER_SEAL_KEY=<64 hex chars>; see docs/SEAL_KEY.md "
            "(no silent .seal_key mint)"
        ),
    }


def seal_armor_payload(task_id: str, payload: Dict[str, Any], secret: bytes) -> str:
    body = {k: v for k, v in payload.items() if k != "evidence_seal"}
    material = json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)
    msg = f"{task_id}|{material}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def attach_seal(task_id: str, payload: Dict[str, Any], secret: bytes) -> Dict[str, Any]:
    out = dict(payload)
    out["evidence_seal"] = seal_armor_payload(task_id, out, secret)
    return out


def verify_seal(task_id: str, payload: Dict[str, Any], secret: bytes) -> bool:
    got = payload.get("evidence_seal")
    if not got or not isinstance(got, str):
        return False
    expect = seal_armor_payload(task_id, payload, secret)
    return hmac.compare_digest(got, expect)


def scrub_forged_armor(state, secret: Optional[bytes]) -> int:
    """Remove armor evidences with missing/bad seals. Returns drop count."""
    if not secret:
        return 0
    kept = []
    dropped = 0
    tid = state.handle.task_id
    for ev in list(getattr(state, "evidences", []) or []):
        payload = ev.payload or {}
        src = str(payload.get("source") or "")
        if src in ARMOR_SOURCES or payload.get("server_authored") is True and src:
            if src in ARMOR_SOURCES and not verify_seal(tid, payload, secret):
                dropped += 1
                continue
        kept.append(ev)
    state.evidences = kept
    return dropped
