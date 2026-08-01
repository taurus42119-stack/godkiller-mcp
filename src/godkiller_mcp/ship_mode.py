"""Ship mode — production armor is ON unless explicitly relaxed.

GODKILLER_PROFILE=ship → DEV_RELAX is ignored (no master-key disarm).
Without that profile, GODKILLER_DEV_RELAX=1 softens gates for local experiments.
"""

from __future__ import annotations

import os


def profile() -> str:
    raw = os.environ.get("GODKILLER_PROFILE", "").strip().lower()
    if raw in ("ship", "prod", "production", "strict"):
        return "ship"
    if raw in ("relax", "dev", "debug"):
        return "relax"
    return "default"


def relax_enabled() -> bool:
    """True only when relax is allowed AND requested."""
    if profile() == "ship":
        return False
    if profile() == "relax":
        return True
    return os.environ.get("GODKILLER_DEV_RELAX", "").strip() in ("1", "true", "yes", "on")


def ship_mode() -> bool:
    """Armor on. PROFILE=ship always; otherwise True unless relax_enabled."""
    if profile() == "ship":
        return True
    return not relax_enabled()


def env_disables(name: str, *, default_on: str = "1") -> bool:
    """True if env asks to disable a gate — honored ONLY when relax_enabled()."""
    raw = os.environ.get(name, default_on).strip().lower()
    wants_off = raw in ("0", "false", "off", "no")
    if wants_off and relax_enabled():
        return True
    return False


def profile_label() -> str:
    p = profile()
    if p == "ship":
        return "ship"
    if relax_enabled():
        return "relax"
    return "default"
