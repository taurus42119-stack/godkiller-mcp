"""SSRF guard — resolve host to IP and block private/link-local/metadata targets.

safe_urlopen pins the resolved public IP for the TCP connect (Host/SNI keep
the original hostname) so a later DNS rebind to loopback cannot hijack the hop.
"""

from __future__ import annotations

import http.client
import ipaddress
import re
import socket
import ssl
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


def _format_connect_host(ip_s: str) -> str:
    ip = ipaddress.ip_address(ip_s)
    if isinstance(ip, ipaddress.IPv6Address):
        return f"[{ip_s}]"
    return ip_s


def resolve_public_ips(host: str, port: int) -> Tuple[bool, str, List[str]]:
    """Resolve host and return only public IPs (fail-closed if any answer is blocked)."""
    h = (host or "").strip().lower()
    if not h:
        return False, "SSRF DENY: missing host", []
    if h in _BLOCKED_HOST_FRAGMENTS or any(x in h for x in _BLOCKED_HOST_FRAGMENTS):
        return False, f"SSRF DENY: blocked host {h}", []

    lit, lit_reason = _literal_ip(h)
    if lit is not None:
        if _is_blocked_ip(lit):
            return False, f"SSRF DENY: blocked IP {lit}", []
        return True, "ok", [str(lit)]
    if lit_reason.startswith("SSRF DENY"):
        return False, lit_reason, []

    try:
        infos = socket.getaddrinfo(h, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return False, f"SSRF DENY: DNS failed for {h}: {exc}", []
    if not infos:
        return False, f"SSRF DENY: no addresses for {h}", []

    seen: List[str] = []
    for info in infos:
        ip_s = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_s)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            return False, f"SSRF DENY: {h} resolves to blocked IP {ip}", []
        if ip_s not in seen:
            seen.append(ip_s)
    if not seen:
        return False, f"SSRF DENY: could not parse addresses for {h}", []
    return True, f"ok resolved={seen[:3]}", seen


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
    port = parsed.port or (443 if scheme == "https" else 80)
    ok, reason, _ips = resolve_public_ips(host, port)
    return ok, reason


def guard_url_or_error(url: str) -> Optional[Dict[str, Any]]:
    ok, reason = assert_public_url(url)
    if ok:
        return None
    return {"ok": False, "error": reason, "ssrf_blocked": True}


def _opener_no_redirect() -> urllib.request.OpenerDirector:
    """Legacy helper kept for tests/callers; prefer pinned safe_urlopen."""
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
    )


class _PinnedResponse:
    """Minimal file-like response compatible with callers of urlopen."""

    def __init__(self, status: int, headers: Dict[str, str], body: bytes):
        self.status = status
        self.headers = headers
        self._body = body
        self._fp = None

    def getcode(self) -> int:
        return self.status

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            out, self._body = self._body, b""
            return out
        out, self._body = self._body[:n], self._body[n:]
        return out

    def close(self) -> None:
        pass

    def __enter__(self) -> "_PinnedResponse":
        return self

    def __exit__(self, *args: Any) -> bool:
        self.close()
        return False


def _request_pinned(
    url: str,
    *,
    timeout: float,
    headers: Dict[str, str],
    data: Any,
    method: Optional[str],
    pinned_ips: List[str],
) -> _PinnedResponse:
    """HTTP(S) request connecting to pinned_ips[0]; Host/SNI use original hostname."""
    parsed = urllib.parse.urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").strip()
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    ip = pinned_ips[0]
    connect_host = _format_connect_host(ip)

    hdrs = {k: v for k, v in headers.items()}
    if "Host" not in hdrs and "host" not in {k.lower() for k in hdrs}:
        hdrs["Host"] = host if not parsed.port else f"{host}:{parsed.port}"

    verb = (method or ("POST" if data is not None else "GET")).upper()
    body = data if data is None or isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")

    if scheme == "https":
        ctx = ssl.create_default_context()
        conn: http.client.HTTPConnection = http.client.HTTPSConnection(
            connect_host,
            port=port,
            timeout=timeout,
            context=ctx,
        )

        def _connect_https() -> None:
            sock = socket.create_connection((ip, port), timeout)
            conn.sock = ctx.wrap_socket(sock, server_hostname=host)

        conn.connect = _connect_https  # type: ignore[method-assign]
    else:
        conn = http.client.HTTPConnection(connect_host, port=port, timeout=timeout)

        def _connect_http() -> None:
            conn.sock = socket.create_connection((ip, port), timeout)

        conn.connect = _connect_http  # type: ignore[method-assign]

    try:
        conn.request(verb, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        # header map (case-insensitive access via dict)
        hdr_map = {k: v for k, v in resp.getheaders()}
        out = _PinnedResponse(resp.status, hdr_map, raw)
        return out
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    Fetch URL with SSRF checks and DNS-pinning on every hop.
    Redirects are followed only when the next URL also passes policy.
    Raises SafeHTTPError on policy deny.
    """
    current = (url or "").strip()
    hdrs = dict(headers or {})
    allow = {h.lower() for h in (allowed_hosts or ())}
    body = data

    for _ in range(max_redirects + 1):
        ok, reason = assert_public_url(current, resolve=False)
        if not ok:
            raise SafeHTTPError(reason)

        parsed = urllib.parse.urlparse(current)
        host = (parsed.hostname or "").strip().lower()
        if allow and host not in allow:
            raise SafeHTTPError(f"SSRF DENY: host not allowlisted: {host}")

        scheme = (parsed.scheme or "").lower()
        port = parsed.port or (443 if scheme == "https" else 80)
        ok_ips, reason_ips, ips = resolve_public_ips(host, port)
        if not ok_ips or not ips:
            raise SafeHTTPError(reason_ips)

        resp = _request_pinned(
            current,
            timeout=timeout,
            headers=hdrs,
            data=body,
            method=method,
            pinned_ips=ips,
        )

        if resp.status in _REDIRECT_CODES:
            loc = None
            for k, v in resp.headers.items():
                if k.lower() == "location":
                    loc = v
                    break
            resp.close()
            if not loc:
                raise SafeHTTPError(f"SSRF DENY: redirect {resp.status} without Location")
            current = urllib.parse.urljoin(current, loc)
            body = None
            continue
        return resp

    raise SafeHTTPError("SSRF DENY: too many redirects")
