"""The corpus fetch guard: only http(s) URLs on public addresses, no network access in tests."""

import socket
import unittest

from public_url import is_public


def resolver(*addresses):
    def resolve(host, port, proto=0):
        return [
            (socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, proto, "", (a, port))
            for a in addresses
        ]

    return resolve


def unresolvable(host, port, proto=0):
    raise socket.gaierror("no such host")


class PublicUrlTest(unittest.TestCase):
    def test_public_http_and_https_are_allowed(self):
        for url in ("https://forms.example.jp/apply", "http://forms.example.jp:8080/entry?x=1"):
            self.assertTrue(is_public(url, resolver("8.8.8.8", "2001:4860:4860::8888")), url)

    def test_non_public_addresses_are_rejected(self):
        for address in (
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "::1",
            "fe80::1%en0",
            "fc00::1",
            "::ffff:127.0.0.1",
        ):
            self.assertFalse(is_public("https://forms.example.jp/", resolver(address)), address)

    def test_one_private_address_rejects_the_host(self):
        self.assertFalse(is_public("https://forms.example.jp/", resolver("8.8.8.8", "127.0.0.1")))

    def test_other_schemes_credentials_and_malformed_urls_are_rejected(self):
        public = resolver("8.8.8.8")
        for url in (
            "file:///etc/passwd",
            "ftp://forms.example.jp/",
            "javascript:alert(1)",
            "https://user:secret@forms.example.jp/",
            "https://forms.example.jp/\nx",
            "--output=/tmp/x",
            "https:///path",
            "https://forms.example.jp:99999/",
            "",
        ):
            self.assertFalse(is_public(url, public), url)

    def test_unresolvable_host_is_rejected(self):
        self.assertFalse(is_public("https://missing.example.jp/", unresolvable))


if __name__ == "__main__":
    unittest.main()
