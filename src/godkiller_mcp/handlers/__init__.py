"""Domain handlers (extracted from dispatch over time).

Kernel paths live in evidence_store / verify_bundle / policy.
Further if-chain splits land here without changing facade names.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

Handler = Callable[[str, Dict[str, Any]], Awaitable[Any]]

# Populated lazily by dispatch to avoid import cycles during migration.
REGISTRY: Dict[str, Handler] = {}


def register(name: str, handler: Handler) -> None:
    REGISTRY[name] = handler
