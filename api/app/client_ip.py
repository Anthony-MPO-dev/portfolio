"""Visitor IP behind Cloudflare.

Responsibility: the site sits behind Cloudflare's proxy, so the connection the app sees comes from a Cloudflare edge
and every visitor at the same edge would share one rate limit. Cloudflare puts the visitor's address in
CF-Connecting-IP. That header is trusted only when the peer is inside Cloudflare's published ranges: anyone calling
the server's IP directly can't fake it. A missing or malformed header falls back to the peer.
Public API: client_ip, ip_source (how the address was read, for the health check), CLOUDFLARE_RANGES.
Used by: app.http (the IP is turned into an HMAC right after).
Depends on: the standard library ipaddress.
Tests: tests/test_client_ip.py.
"""

from collections.abc import Mapping
from ipaddress import ip_address, ip_network

# https://www.cloudflare.com/ips-v4 and /ips-v6, fetched 2026-11-06
CLOUDFLARE_RANGES = tuple(
    ip_network(cidr)
    for cidr in (
        "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18",
        "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17",
        "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
        "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32",
        "2a06:98c0::/29", "2c0f:f248::/32",
    )
)  # fmt: skip


def _ip(value: str):
    try:
        return ip_address(value.strip())
    except ValueError:
        return None


def _resolve(peer: str, headers: Mapping[str, str]) -> tuple[str, str]:
    peer_ip = _ip(peer)
    if peer_ip is None:
        return peer, "unknown"
    if any(peer_ip in net for net in CLOUDFLARE_RANGES):
        visitor = _ip(headers.get("cf-connecting-ip", ""))
        return (str(visitor), "cloudflare") if visitor else (peer, "shared")
    return peer, "shared" if peer_ip.is_private or peer_ip.is_loopback else "direct"


def client_ip(peer: str, headers: Mapping[str, str]) -> str:
    return _resolve(peer, headers)[0]


def ip_source(peer: str, headers: Mapping[str, str]) -> str:
    """Whose address client_ip used: "cloudflare" (the visitor's, from the header), "direct" (a direct caller's own),
    "shared" (a proxy's or a Cloudflare edge's, so many visitors would share one rate limit) or "unknown"."""
    return _resolve(peer, headers)[1]
