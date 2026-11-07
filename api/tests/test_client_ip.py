"""Visitor IP behind Cloudflare: trust CF-Connecting-IP only when the connection really comes from Cloudflare."""

import pytest

from app.client_ip import client_ip, ip_source

CLOUDFLARE_PEERS = ["162.158.10.1", "2606:4700::1"]


@pytest.mark.parametrize("peer", CLOUDFLARE_PEERS)
def test_behind_cloudflare_the_visitor_ip_comes_from_its_header(peer):
    assert client_ip(peer, {"cf-connecting-ip": "203.0.113.7"}) == "203.0.113.7"


def test_direct_connection_cannot_fake_the_header():
    assert client_ip("198.51.100.9", {"cf-connecting-ip": "203.0.113.7"}) == "198.51.100.9"


@pytest.mark.parametrize("header", [{}, {"cf-connecting-ip": "not-an-ip"}, {"cf-connecting-ip": "1.2.3.4, 5.6.7.8"}])
def test_missing_or_malformed_header_falls_back_to_the_peer(header):
    assert client_ip("162.158.10.1", header) == "162.158.10.1"


def test_unknown_peer_is_kept_as_is():
    assert client_ip("testclient", {}) == "testclient"


@pytest.mark.parametrize(
    "peer, headers, source",
    [
        ("162.158.10.1", {"cf-connecting-ip": "203.0.113.7"}, "cloudflare"),  # the visitor's own address
        ("93.184.215.14", {"cf-connecting-ip": "203.0.113.7"}, "direct"),  # a direct connection: its own address
        ("10.0.1.5", {"cf-connecting-ip": "203.0.113.7"}, "shared"),  # a proxy's address: every visitor alike
        ("127.0.0.1", {}, "shared"),
        ("162.158.10.1", {}, "shared"),  # a Cloudflare edge without the header: all visitors at that edge
        ("testclient", {}, "unknown"),
    ],
)
def test_the_source_says_whose_address_keys_the_rate_limit(peer, headers, source):
    assert ip_source(peer, headers) == source
