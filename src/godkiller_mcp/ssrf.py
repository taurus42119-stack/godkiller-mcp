"""SSRF guard — resolve host to IP and block private/link-local/metadata targets.

Also provides safe_urlopen: hop-by-hop redirect revalidation (no TOCTOU via Location→private).
"""

from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

_BLOCKED_HOST_FRAGMENTS = (
    "localhost",
    "metadata.google.internal",
    "metadata.google",
)

# Octal / hex dotted quads (0177.0.0.1, 0x7f.0.0.1) — browsers may reinterpret
_WEIRD_DOTTED = re.compile(
    r"^(?:0[0-7]+|0x[0-9a-fA-F]+)(?:\.(?:0[0-7]+|0x[0-9a-fA-F]+|\d+)){3}$"
)

_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class SafeHTTPError(Exception):
    """Raised when SSRF policy blocks a fetch (including redirect hops)."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        return _is_blocked_ip(mapped)
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        return True
    if ip.is_multicast or ip.is_unspecified:
        return True
    if str(ip) in ("169.254.169.254", "fd00:ec2::254"):
        return True
    return False


def _literal_ip(host: str) -> Tuple[Optional[ipaddress.IPv4Address | ipaddress.IPv6Address], str]:
    """Parse host as IP; reject weird notations that bypass naive filters."""
    h = (host or "").strip().lower()
    if not h:
        return None, "empty host"
    if _WEIRD_DOTTED.match(h):
        return None, "SSRF DENY: octal/hex dotted IP notation blocked"
    # Pure integer / hex integer forms (e.g. 2130706433, 0x7f000001)
    if re.fullmatch(r"0x[0-9a-f]+", h) or (h.isdigit() and len(h) >= 4):
        try:
            val = int(h, 0) if h.startswith("0x") else int(h)
            ip = ipaddress.ip_address(val)
            return ip, "ok"
        except (ValueError, OverflowError):
            return None, "SSRF DENY: invalid numeric IP"
    try:
        return ipaddress.ip_address(h), "ok"
    except ValueError:
        return None, "not_literal"


_BLOCKED_SCHEMES = frozenset(
    {
        "file",
        "gopher",
        "dict",
        "ftp",
        "ftps",
        "jar",
        "data",
        "php",
        "ldap",
        "ldaps",
        "mailto",
        "telnet",
        "ssh",
        "sftp",
        "ws",
        "wss",
    }
)


def assert_public_url(url: str, *, resolve: bool = True) -> Tuple[bool, str]:
    """Return (ok, reason). Fail-closed on parse/resolve errors when resolve=True."""
    raw = (url or "").strip()
    if not raw:
        return False, "SSRF DENY: empty URL"
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception as exc:
        return False, f"SSRF DENY: bad URL ({exc})"
    scheme = (parsed.scheme or "").strip().lower()
    if not scheme:
        return False, "SSRF DENY: missing URL scheme"
    if scheme in _BLOCKED_SCHEMES:
        return False, f"SSRF DENY: scheme '{scheme}' blocked (protocol smuggling)"
    if scheme not in ("http", "https"):
        return False, f"SSRF DENY: only http(s) URLs allowed (got '{scheme}')"
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False, "SSRF DENY: missing host"
    if host in _BLOCKED_HOST_FRAGMENTS or any(h in host for h in _BLOCKED_HOST_FRAGMENTS):
        return False, f"SSRF DENY: blocked host {host}"

    lit, lit_reason = _literal_ip(host)
    if lit is not None:
        if _is_blocked_ip(lit):
            return False, f"SSRF DENY: blocked IP {lit}"
        return True, "ok"
    if lit_reason.startswith("SSRF DENY"):
        return False, lit_reason

    if not resolve:
        return True, "ok (no resolve)"
    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return False, f"SSRF DENY: DNS failed for {host}: {exc}"
    if not infos:
        return False, f"SSRF DENY: no addresses for {host}"
    seen: List[str] = []
    for info in infos:
        sockaddr = info[4]
        ip_s = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            continue
        seen.append(str(ip))
        if _is_blocked_ip(ip):
            return False, f"SSRF DENY: {host} resolves to blocked IP {ip}"
    if not seen:
        return False, f"SSRF DENY: could not parse addresses for {host}"
    return True, f"ok resolved={seen[:3]}"


def guard_url_or_error(url: str) -> Optional[Dict[str, Any]]:
    ok, reason = assert_public_url(url)
    if ok:
        return None
    return {"ok": False, "error": reason, "ssrf_blocked": True}


def _opener_no_redirect() -> urllib.request.OpenerDirector:
    """Opener without HTTPRedirectHandler — caller revalidates each Location."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
    )


def safe_urlopen(
    url: str,
    *,
    timeout: float = 10.0,
    headers: Optional[Dict[str, str]] = None,
    max_redirects: int = 5,
    data: Any = None,
    method: Optional[str] = None,
    allowed_hosts: Optional[Sequence[str]] = None,
):
    """
    Fetch URL with assert_public_url on every hop.
    Redirects are followed manually only when the next URL also passes SSRF
    (and optional host allowlist). Raises SafeHTTPError on policy deny.
    """
    current = (url or "").strip()
    hdrs = dict(headers or {})
    allow = {h.lower() for h in (allowed_hosts or ())}
    opener = _opener_no_redirect()
    body = data

    for _ in range(max_redirects + 1):
        ok, reason = assert_public_url(current, resolve=True)
        if not ok:
            raise SafeHTTPError(reason)
        if allow:
            host = (urllib.parse.urlparse(current).hostname or "").lower()
            if host not in allow:
                raise SafeHTTPError(f"SSRF DENY: host not allowlisted: {host}")

        req = urllib.request.Request(current, data=body, headers=hdrs, method=method)
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECT_CODES:
                loc = exc.headers.get("Location") if exc.headers else None
                if not loc:
                    raise SafeHTTPError(f"SSRF DENY: redirect {exc.code} without Location") from exc
                current = urllib.parse.urljoin(current, loc)
                body = None
                try:
                    exc.close()
                except Exception:
                    pass
                continue
            raise

        code = getattr(resp, "status", None) or resp.getcode()
        if code in _REDIRECT_CODES:
            loc = resp.headers.get("Location") if resp.headers else None
            try:
                resp.close()
            except Exception:
                pass
            if not loc:
                raise SafeHTTPError(f"SSRF DENY: redirect {code} without Location")
            current = urllib.parse.urljoin(current, loc)
            body = None
            continue
        return resp

    raise SafeHTTPError("SSRF DENY: too many redirects")
