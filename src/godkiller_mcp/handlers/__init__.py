"""Domain handlers (extracted from dispatch over time).

Kernel paths live in evidence_store / verify_bundle / policy.
Further if-chain splits land here without changing facade names.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

Handler = Callable[[str, Dict[str, Any]], Awaitable[Any]]

# Populated by ensure_registered() — avoid import cycles during module load.
REGISTRY: Dict[str, Handler] = {}

_registered = False


def register(name: str, handler: Handler) -> None:
    REGISTRY[name] = handler


def ensure_registered() -> None:
    """Idempotent: load peeled handler modules into REGISTRY."""
    global _registered
    if _registered:
        return
    from godkiller_mcp.handlers import (
        code_intel_tools,
        edit_safe,
        modes_ultradeep,
        task,
        verify,
        visual_marathon,
    )

    task.register()
    edit_safe.register()
    verify.register()
    code_intel_tools.register()
    modes_ultradeep.register()
    visual_marathon.register()
    _registered = True
