#!/usr/bin/env python3
"""Unit tests for the crawler's entire navigation safety boundary (see link_filter.py's
docstring): only <a href> targets are ever followed, and only if they're same-origin. No browser
or live router needed — pure HTML fixtures in, link lists out.
"""
import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawler")
)

from pennypincher_crawler.link_filter import normalize_url, same_origin_links  # noqa: E402

BASE_URL = "http://192.168.1.1/status.html"
ORIGIN = "192.168.1.1"


class SameOriginLinksTests(unittest.TestCase):
    def test_follows_relative_and_absolute_same_origin_anchors(self):
        html = """
            <nav>
                <a href="/wifi.html">WiFi</a>
                <a href="lan.html">LAN</a>
                <a href="http://192.168.1.1/firewall.html">Firewall</a>
            </nav>
        """
        links = same_origin_links(html, BASE_URL, ORIGIN)
        self.assertIn("http://192.168.1.1/wifi.html", links)
        self.assertIn("http://192.168.1.1/lan.html", links)
        self.assertIn("http://192.168.1.1/firewall.html", links)

    def test_excludes_off_origin_links(self):
        html = '<a href="https://vendor.example.com/support">Support</a>'
        links = same_origin_links(html, BASE_URL, ORIGIN)
        self.assertEqual(links, [])

    def test_excludes_non_anchor_navigation(self):
        # A "Reboot" control implemented as a button/onclick handler, not an <a href> — must be
        # completely invisible to link extraction, since that's the crawler's only navigation
        # source. No button or form (other than login) is ever interacted with.
        html = """
            <button onclick="location.href='/reboot.cgi'">Reboot</button>
            <form action="/reset.cgi" method="post"><input type="submit" value="Factory Reset"></form>
            <a href="/settings.html">Settings</a>
        """
        links = same_origin_links(html, BASE_URL, ORIGIN)
        self.assertEqual(links, ["http://192.168.1.1/settings.html"])

    def test_excludes_non_http_schemes(self):
        html = '<a href="mailto:support@example.com">Email</a><a href="javascript:void(0)">JS</a>'
        links = same_origin_links(html, BASE_URL, ORIGIN)
        self.assertEqual(links, [])


class NormalizeUrlTests(unittest.TestCase):
    def test_trailing_slash_and_fragment_collapse_to_same_url(self):
        self.assertEqual(
            normalize_url("http://192.168.1.1/wifi.html/"),
            normalize_url("http://192.168.1.1/wifi.html#panel"),
        )

    def test_root_path_variants_are_equal(self):
        self.assertEqual(normalize_url("http://192.168.1.1"), normalize_url("http://192.168.1.1/"))


if __name__ == "__main__":
    unittest.main()
