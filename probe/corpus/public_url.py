#!/usr/bin/env python3
"""Exit 0 only for an http(s) URL whose host resolves to public addresses.

Usage: public_url.py <url>   The corpus tools fetch URLs taken from untrusted pages; this keeps
them off loopback, private, link-local and other non-public hosts (local dev servers, routers,
adb and DevTools forwards).
"""

import ipaddress
import socket
import sys
from urllib.parse import urlsplit


def is_public(url, resolve=socket.getaddrinfo):
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url):
        return False
    try:
        parts = urlsplit(url)
        host, port = parts.hostname, parts.port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
        return False
    try:
        infos = resolve(host, port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        addresses = {ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos}
    except (OSError, UnicodeError, ValueError):
        return False
    return bool(addresses) and all(address.is_global for address in addresses)


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 2 and is_public(sys.argv[1]) else 1)
