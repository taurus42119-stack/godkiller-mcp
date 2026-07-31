"""Pytest defaults — quiet seal + offline DOI for deterministic CI."""

from __future__ import annotations

import os

# Import-time defaults so module-level EvidenceStore construction during collection works.
os.environ.setdefault("GODKILLER_SEAL_QUIET", "1")
os.environ.setdefault("GODKILLER_DOI_RESOLVE", "0")
os.environ.setdefault("GODKILLER_QUOTE_BIND", "0")
if not os.environ.get("GODKILLER_SEAL_KEY"):
    os.environ["GODKILLER_SEAL_KEY"] = "00" * 32

import pytest


@pytest.fixture(scope="session", autouse=True)
def _godkiller_test_env() -> None:
    os.environ.setdefault("GODKILLER_SEAL_QUIET", "1")
    os.environ.setdefault("GODKILLER_DOI_RESOLVE", "0")
    os.environ.setdefault("GODKILLER_QUOTE_BIND", "0")
    if not os.environ.get("GODKILLER_SEAL_KEY"):
        os.environ["GODKILLER_SEAL_KEY"] = "00" * 32
