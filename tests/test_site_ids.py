#!/usr/bin/env python3
"""Tests for address -> site_id slugging and site reuse (backend/sites.py). Runs against a
temporary data directory, not the real data/ folder.
"""
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.sites as sites  # noqa: E402


class SiteIdTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = sites.DATA_DIR
        sites.DATA_DIR = Path(self._tmpdir.name)

    def tearDown(self):
        sites.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def test_slug_is_readable_and_deterministic(self):
        site_id = sites.site_id_for("123 Main St, Springfield")
        self.assertTrue(site_id.startswith("123-main-st-springfield-"))
        self.assertEqual(site_id, sites.site_id_for("123 Main St, Springfield"))

    def test_case_and_whitespace_insensitive_reuse(self):
        first = sites.get_or_create_site("123 Main St, Springfield")
        second = sites.get_or_create_site("  123 MAIN ST, Springfield  ")
        self.assertEqual(first, second)

    def test_creating_twice_does_not_overwrite_notes(self):
        site_id = sites.get_or_create_site("456 Oak Ave", notes="gate code 1234")
        sites.get_or_create_site("456 Oak Ave", notes=None)
        site = sites.get_site(site_id)
        self.assertEqual(site["notes"], "gate code 1234")

    def test_different_addresses_get_different_ids(self):
        a = sites.get_or_create_site("1 First St")
        b = sites.get_or_create_site("2 Second St")
        self.assertNotEqual(a, b)

    def test_get_site_reports_scan_count(self):
        site_id = sites.get_or_create_site("789 Pine Rd")
        (sites.DATA_DIR / site_id / "scans" / "scan1").mkdir(parents=True)
        (sites.DATA_DIR / site_id / "scans" / "scan2").mkdir(parents=True)
        site = sites.get_site(site_id)
        self.assertEqual(site["scan_count"], 2)
        self.assertEqual(site["last_scan_at"], "scan2")

    def test_get_site_missing_returns_none(self):
        self.assertIsNone(sites.get_site("nonexistent"))

    def test_list_sites(self):
        sites.get_or_create_site("1 First St")
        sites.get_or_create_site("2 Second St")
        listed = {s["address"] for s in sites.list_sites()}
        self.assertEqual(listed, {"1 First St", "2 Second St"})


if __name__ == "__main__":
    unittest.main()
