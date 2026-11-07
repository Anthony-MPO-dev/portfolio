"""Visitor IP behind Cloudflare: trust CF-Connecting-IP only when the connection really comes from Cloudflare."""

import pytest

from app.client_ip import client_ip

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
