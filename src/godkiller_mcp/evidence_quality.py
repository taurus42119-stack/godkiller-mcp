"""Anti-theatre text/URL quality — kill asdfasdf / nits / fake-shaped cites."""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import urlparse

_HOLLOW_WORDS = frozenset(
    {
        "nits",
        "nit",
        "typo",
        "ok",
        "fine",
        "lgtm",
        "todo",
        "tbd",
        "asdf",
        "qwer",
        "test",
        "placeholder",
        "lorem",
        "ipsum",
        "xxx",
        "yyy",
        "zzz",
        "foo",
        "bar",
        "baz",
    }
)

_DOI_RE = re.compile(r"^(?:doi:)?10\.\d{4,9}/[-._;()/:A-Z0-9]+$", re.I)


def normalize_finding(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_hollow_text(text: str, *, min_chars: int = 16, min_unique_words: int = 4) -> Tuple[bool, str]:
    """Return (hollow, reason)."""
    s = (text or "").strip()
    if len(s) < min_chars:
        return True, f"too short (<{min_chars})"
    # repeated character spam
    if re.search(r"(.)\1{6,}", s):
        return True, "repeated-char spam"
    # low alphabet diversity
    letters = re.findall(r"[a-zA-Zก-๙]", s)
    if letters and len(set(c.lower() for c in letters)) < 5 and len(s) >= 20:
        return True, "low character diversity"
    words = [w for w in re.split(r"[^\wก-๙]+", s.lower()) if w]
    if len(set(words)) < min_unique_words:
        return True, f"need ≥{min_unique_words} distinct words"
    if all(w in _HOLLOW_WORDS or len(w) <= 2 for w in words):
        return True, "hollow/boilerplate tokens only"
    # keyboard-walk fragments
    low = s.lower()
    for bad in ("asdf", "qwer", "zxcv", "lorem ipsum", "coming soon"):
        if bad in low:
            return True, f"hollow fragment: {bad}"
    return False, "ok"


def dedupe_findings(lines: Sequence[str]) -> Tuple[List[str], int]:
    """Drop near-duplicates; return (unique, dropped_count)."""
    seen = set()
    out: List[str] = []
    dropped = 0
    for line in lines:
        key = normalize_finding(line)[:120]
        if not key or key in seen:
            dropped += 1
            continue
        # near-dup: share long prefix with existing
        if any(key[:40] == s[:40] for s in seen if len(s) >= 40):
            dropped += 1
            continue
        seen.add(key)
        out.append(line)
    return out, dropped


def cite_source_ok(src: str) -> Tuple[bool, str]:
    s = (src or "").strip()
    if not s:
        return False, "empty source"
    if s.lower().startswith("doi:"):
        s = s[4:].strip()
    if s.startswith("10."):
        if not re.match(r"^10\.\d{4,9}/\S+$", s):
            return False, "DOI shape invalid (need 10.xxxx/suffix)"
        return True, "doi"
    if not (s.startswith("http://") or s.startswith("https://")):
        return False, "need http(s) URL or DOI"
    try:
        p = urlparse(s)
    except Exception:
        return False, "bad URL"
    host = (p.hostname or "").lower()
    if not host or "." not in host:
        return False, "URL host must look real (has a dot)"
    if host in ("example.com", "example.org", "example.net", "test.com", "localhost"):
        return False, f"placeholder host blocked: {host}"
    if any(host.endswith(x) for x in (".local", ".internal", ".lan")):
        return False, f"private-looking host blocked: {host}"
    return True, "url"


def unique_hosts(urls: Iterable[str]) -> int:
    hosts = set()
    for u in urls:
        try:
            h = (urlparse(u).hostname or "").lower()
            if h:
                hosts.add(h)
        except Exception:
            pass
    return len(hosts)
