#!/usr/bin/env python3
"""Unit tests for the nav-click exploration feature's label-based pre-filter
(crawler/pennypincher_crawler/click_filter.py). This is only the first of two safety layers —
router_spider.py also blocks every non-GET network request during any exploratory click — but
this pure-Python half needs no browser to test.
"""
import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawler")
)

from pennypincher_crawler.click_filter import is_dangerous_label  # noqa: E402


class DangerousLabelTests(unittest.TestCase):
    def test_flags_obvious_danger_words(self):
        for label in ("Reboot", "Factory Reset", "Restart Router", "Delete All Devices",
                       "Apply Changes", "Save Settings", "Sign Out", "Firmware Update"):
            self.assertTrue(is_dangerous_label(label), f"{label!r} should be flagged")

    def test_case_insensitive(self):
        self.assertTrue(is_dangerous_label("REBOOT NOW"))
        self.assertTrue(is_dangerous_label("reboot now"))

    def test_allows_benign_nav_labels(self):
        for label in ("Connected Devices", "WiFi Settings", "Modem Mode", "Admin", "Home",
                       "Advanced Settings", "Diagnostics"):
            self.assertFalse(is_dangerous_label(label), f"{label!r} should be allowed")

    def test_empty_or_none_is_not_dangerous(self):
        self.assertFalse(is_dangerous_label(""))
        self.assertFalse(is_dangerous_label(None))


if __name__ == "__main__":
    unittest.main()
