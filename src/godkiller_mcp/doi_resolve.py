"""Live DOI resolution — Crossref first, OpenAlex fallback.

Used by /view cite gates so fake 10.xxxx/… strings do not count.
Offline/dev: GODKILLER_DOI_RESOLVE=0 → shape-only (explicit).
Default: resolve on (fail-closed on network/404).

Quote binding (GODKILLER_QUOTE_BIND, default on when resolve on):
real DOI + fabricated quote must fail unless quote tokens hit title/abstract
or `page_excerpt` contains the quote (agent-scraped passage).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple

_DOI_BODY = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
_JATS = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[a-z0-9]{4,}", re.I)
_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "were",
        "their",
        "which",
        "about",
        "into",
        "than",
        "then",
        "also",
        "such",
        "using",
        "used",
        "based",
        "results",
        "method",
        "methods",
        "paper",
        "study",
        "https",
        "http",
    }
)

# Only these hosts for DOI APIs (no open SSRF via attacker-controlled DOI redirect follow)
_ALLOWED_API_HOSTS = frozenset(
    {
        "api.crossref.org",
        "api.openalex.org",
    }
)


def normalize_doi(raw: str) -> str:
    s = (raw or "").strip()
    if s.lower().startswith("doi:"):
        s = s[4:].strip()
    if s.lower().startswith("https://doi.org/"):
        s = s[16:].strip()
    if s.lower().startswith("http://doi.org/"):
        s = s[15:].strip()
    return s.strip().rstrip(".")


def doi_shape_ok(doi: str) -> bool:
    return bool(_DOI_BODY.match(normalize_doi(doi)))


def resolve_enabled() -> bool:
    """Live DOI resolve. PROFILE=ship ignores GODKILLER_DOI_RESOLVE=0 (no weaken)."""
    from godkiller_mcp.ship_mode import profile

    v = os.environ.get("GODKILLER_DOI_RESOLVE", "1").strip().lower()
    if v in ("0", "false", "off", "no"):
        if profile() == "ship":
            return True
        return False
    return True


def resolve_doi(raw: str, *, timeout: float = 8.0) -> Dict[str, Any]:
    """
    Return {ok, doi, title?, container?, source?, reason?}.
    Fail-closed when resolve enabled and lookup fails.
    """
    doi = normalize_doi(raw)
    if not doi_shape_ok(doi):
        return {"ok": False, "doi": doi, "reason": "DOI shape invalid"}
    if not resolve_enabled():
        return {
            "ok": True,
            "doi": doi,
            "source": "shape_only",
            "reason": "GODKILLER_DOI_RESOLVE=0 — shape accepted without live lookup",
        }

    cross = _fetch_crossref(doi, timeout=timeout)
    if cross.get("ok"):
        return cross
    alex = _fetch_openalex(doi, timeout=timeout)
    if alex.get("ok"):
        return alex
    return {
        "ok": False,
        "doi": doi,
        "reason": (
            f"DOI not resolved via Crossref/OpenAlex "
            f"(crossref={cross.get('reason')}; openalex={alex.get('reason')})"
        ),
        "crossref": cross,
        "openalex": alex,
    }


def cite_with_doi_policy(src: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    For sources that look like DOI: live resolve when enabled.
    For http(s): return deferred (caller still does SSRF/shape).
    """
    s = (src or "").strip()
    low = s.lower()
    if (
        low.startswith("doi:")
        or low.startswith("10.")
        or "doi.org/" in low
    ):
        result = resolve_doi(s)
        if not result.get("ok"):
            return False, str(result.get("reason") or "DOI resolve failed"), result
        return True, f"doi ok via {result.get('source')}", result
    return True, "not_doi", {}


def quote_bind_enabled() -> bool:
    """Default follows DOI resolve: bind on when live resolve is on."""
    from godkiller_mcp.ship_mode import profile

    explicit = os.environ.get("GODKILLER_QUOTE_BIND", "").strip().lower()
    if explicit in ("0", "false", "off", "no"):
        if profile() == "ship":
            return True
        return False
    if explicit in ("1", "true", "on", "yes"):
        return True
    return resolve_enabled()


def _significant_tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in _STOP}


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _openalex_abstract(inv: Any) -> str:
    if not isinstance(inv, dict) or not inv:
        return ""
    pairs: list[tuple[int, str]] = []
    for word, positions in inv.items():
        if not isinstance(positions, list):
            continue
        for p in positions:
            try:
                pairs.append((int(p), str(word)))
            except (TypeError, ValueError):
                continue
    pairs.sort()
    return " ".join(w for _, w in pairs)


def quote_bound_to_record(
    quote: str,
    meta: Dict[str, Any],
    *,
    page_excerpt: str = "",
) -> Tuple[bool, str]:
    """
    Block real-DOI + fake-quote theatre.
    Pass if: bind off / shape_only / non-DOI meta empty;
    or quote ⊆ page_excerpt; or enough token overlap with title+abstract+container.
    """
    if not quote_bind_enabled():
        return True, "bind_off"
    if not meta or meta.get("source") == "shape_only":
        return True, "shape_only_skip_bind"
    # Non-DOI path leaves empty meta from cite_with_doi_policy
    if not meta.get("doi") and not meta.get("title") and not meta.get("abstract"):
        return True, "not_doi_meta"

    excerpt = (page_excerpt or "").strip()
    q = (quote or "").strip()
    if excerpt:
        if _norm_space(q) in _norm_space(excerpt):
            return True, "quote_in_excerpt"
        return False, "quote not found in page_excerpt"

    abstract = str(meta.get("abstract") or "").strip()
    abs_tok = _significant_tokens(abstract)
    # Round 2: thin abstract cannot alone vouch for a quote — require page_excerpt
    thin_abstract = len(abstract) < 80 or len(abs_tok) < 8
    if thin_abstract:
        return False, (
            "abstract thin — pass page_excerpt containing the cited passage "
            f"(abstract_chars={len(abstract)} abs_tokens={len(abs_tok)})"
        )

    blob = " ".join(
        [
            str(meta.get("title") or ""),
            str(meta.get("container") or ""),
            abstract,
        ]
    ).strip()
    if not blob:
        return False, (
            "DOI resolved but no title/abstract to bind quote — "
            "pass page_excerpt containing the cited passage"
        )

    qtok = _significant_tokens(q)
    btok = _significant_tokens(blob)
    if not qtok:
        return False, "quote has no significant tokens for bind"
    overlap = qtok & btok
    need = 2 if len(btok) >= 12 else 1
    if len(overlap) >= need:
        return True, f"token_overlap={sorted(overlap)[:8]}"
    return False, (
        f"quote not supported by title/abstract (overlap={len(overlap)} need≥{need}); "
        "pass page_excerpt with the cited passage"
    )


def _get_json(url: str, *, timeout: float) -> Tuple[Optional[dict], str]:
    from godkiller_mcp.ssrf import SafeHTTPError, safe_urlopen

    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_API_HOSTS:
        return None, f"API host not allowlisted: {host}"
    try:
        with safe_urlopen(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "godkiller-mcp/doi-resolve (mailto:devnull@example.com)",
                "Accept": "application/json",
            },
            allowed_hosts=_ALLOWED_API_HOSTS,
        ) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return json.loads(raw), "ok"
    except SafeHTTPError as exc:
        return None, exc.reason
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)[:200]


def _fetch_crossref(doi: str, *, timeout: float) -> Dict[str, Any]:
    enc = urllib.parse.quote(doi, safe="")
    url = f"https://api.crossref.org/works/{enc}"
    data, err = _get_json(url, timeout=timeout)
    if not data:
        return {"ok": False, "doi": doi, "source": "crossref", "reason": err}
    msg = data.get("message") or {}
    title_l = msg.get("title") or []
    title = title_l[0] if title_l else ""
    container_l = msg.get("container-title") or []
    raw_abs = msg.get("abstract") or ""
    if isinstance(raw_abs, list):
        raw_abs = " ".join(str(x) for x in raw_abs)
    abstract = _JATS.sub(" ", str(raw_abs))
    abstract = re.sub(r"\s+", " ", abstract).strip()[:8000]
    if not title and not msg.get("DOI"):
        return {"ok": False, "doi": doi, "source": "crossref", "reason": "empty Crossref message"}
    return {
        "ok": True,
        "doi": normalize_doi(str(msg.get("DOI") or doi)),
        "title": str(title)[:300],
        "container": str(container_l[0] if container_l else "")[:200],
        "abstract": abstract,
        "source": "crossref",
    }


def _fetch_openalex(doi: str, *, timeout: float) -> Dict[str, Any]:
    # OpenAlex work id form
    enc = urllib.parse.quote(f"https://doi.org/{doi}", safe="")
    url = f"https://api.openalex.org/works/{enc}"
    data, err = _get_json(url, timeout=timeout)
    if not data:
        return {"ok": False, "doi": doi, "source": "openalex", "reason": err}
    title = str(data.get("display_name") or data.get("title") or "")[:300]
    abstract = _openalex_abstract(data.get("abstract_inverted_index"))[:8000]
    if not title and not data.get("doi"):
        return {"ok": False, "doi": doi, "source": "openalex", "reason": "empty OpenAlex work"}
    return {
        "ok": True,
        "doi": normalize_doi(str(data.get("doi") or doi).replace("https://doi.org/", "")),
        "title": title,
        "container": "",
        "abstract": abstract,
        "source": "openalex",
    }
