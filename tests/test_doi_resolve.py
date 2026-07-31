"""P4 DOI live resolve — Crossref/OpenAlex (mocked in unit tests)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from godkiller_mcp.doi_resolve import cite_with_doi_policy, normalize_doi, resolve_doi


def test_normalize_doi():
    assert normalize_doi("doi:10.1234/abc") == "10.1234/abc"
    assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"


def test_shape_only_when_resolve_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "0")
    r = resolve_doi("10.1234/fake.journal.xyz")
    assert r["ok"] is True
    assert r["source"] == "shape_only"


def test_live_resolve_crossref_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "1")
    payload = {
        "message": {
            "DOI": "10.1038/nature14539",
            "title": ["Deep learning"],
            "container-title": ["Nature"],
        }
    }

    class _Resp:
        def read(self):
            return json.dumps(payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with patch("godkiller_mcp.doi_resolve.urllib.request.urlopen", return_value=_Resp()):
        r = resolve_doi("10.1038/nature14539")
    assert r["ok"] is True
    assert r["source"] == "crossref"
    assert "Deep learning" in r["title"]


def test_live_resolve_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "1")

    def boom(*a, **k):
        raise TimeoutError("no net")

    with patch("godkiller_mcp.doi_resolve.urllib.request.urlopen", side_effect=boom):
        r = resolve_doi("10.9999/does.not.exist.zz")
    assert r["ok"] is False


def test_cite_policy_blocks_bad_doi(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_DOI_RESOLVE", "1")
    with patch(
        "godkiller_mcp.doi_resolve.resolve_doi",
        return_value={"ok": False, "reason": "DOI not resolved"},
    ):
        ok, why, _ = cite_with_doi_policy("10.9999/bogus")
    assert ok is False
    assert "not resolved" in why.lower() or "DOI" in why


def test_quote_bind_rejects_fake_quote(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_QUOTE_BIND", "1")
    from godkiller_mcp.doi_resolve import quote_bound_to_record

    meta = {
        "ok": True,
        "doi": "10.1038/nature14539",
        "title": "Deep learning",
        "abstract": (
            "Neural networks learn hierarchical representations from data across "
            "vision speech and language benchmarks with substantial empirical gains."
        ),
        "source": "crossref",
    }
    ok, why = quote_bound_to_record(
        "Completely unrelated claim about purple unicorn databases and soap.",
        meta,
    )
    assert ok is False
    assert "page_excerpt" in why or "overlap" in why


def test_quote_bind_accepts_abstract_overlap(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_QUOTE_BIND", "1")
    from godkiller_mcp.doi_resolve import quote_bound_to_record

    meta = {
        "ok": True,
        "doi": "10.1038/nature14539",
        "title": "Deep learning",
        "abstract": (
            "Neural networks learn hierarchical representations from data across "
            "vision speech and language benchmarks with substantial empirical gains."
        ),
        "source": "crossref",
    }
    ok, why = quote_bound_to_record(
        "Neural networks learn hierarchical representations from data samples.",
        meta,
    )
    assert ok is True
    assert "overlap" in why


def test_quote_bind_requires_excerpt_when_abstract_thin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_QUOTE_BIND", "1")
    from godkiller_mcp.doi_resolve import quote_bound_to_record

    meta = {
        "ok": True,
        "doi": "10.1038/nature14539",
        "title": "Deep learning",
        "abstract": "Short abstract.",
        "source": "crossref",
    }
    ok, why = quote_bound_to_record(
        "Neural networks learn hierarchical representations from data samples.",
        meta,
    )
    assert ok is False
    assert "abstract thin" in why


def test_quote_bind_accepts_page_excerpt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GODKILLER_QUOTE_BIND", "1")
    from godkiller_mcp.doi_resolve import quote_bound_to_record

    meta = {
        "ok": True,
        "doi": "10.1038/nature14539",
        "title": "Deep learning",
        "abstract": "Short abstract without body quote.",
        "source": "crossref",
    }
    quote = "We trained a model that outperformed previous benchmarks on ImageNet."
    ok, why = quote_bound_to_record(
        quote,
        meta,
        page_excerpt=f"Intro. {quote} Conclusion follows.",
    )
    assert ok is True
    assert why == "quote_in_excerpt"
