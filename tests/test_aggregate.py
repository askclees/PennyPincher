#!/usr/bin/env python3
"""Tests for backend/scans.py::get_aggregate() — merging every completed scan of a given type at
a site into one deduplicated list. Runs against a temporary data directory, building fake
status.json/manifest.json files directly rather than actually running a scan.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.scans as scans  # noqa: E402


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_sites_dir = scans.SITES_DIR
        scans.SITES_DIR = Path(self._tmpdir.name)
        self.site_id = "test-site"

    def tearDown(self):
        scans.SITES_DIR = self._original_sites_dir
        self._tmpdir.cleanup()

    def _write_scan(self, scan_id, scan_type, status, started_at, manifest):
        scan_dir = scans.SITES_DIR / self.site_id / "scans" / scan_id
        scan_dir.mkdir(parents=True)
        (scan_dir / "status.json").write_text(json.dumps({
            "scan_type": scan_type, "status": status, "started_at": started_at,
        }))
        (scan_dir / "manifest.json").write_text(json.dumps(manifest))

    def test_merges_networks_across_two_scans(self):
        self._write_scan("scan1", "wifi_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"ssid": "HomeWifi", "bssid": "AA:BB:CC:DD:EE:01", "signal": 60},
            {"ssid": "CafeGuest", "bssid": "AA:BB:CC:DD:EE:02", "signal": 40},
        ])
        self._write_scan("scan2", "wifi_scan", "done", "2026-01-02T00:00:00+00:00", [
            {"ssid": "HomeWifi", "bssid": "AA:BB:CC:DD:EE:01", "signal": 75},
            {"ssid": "OfficeNet", "bssid": "AA:BB:CC:DD:EE:03", "signal": 90},
        ])

        result = scans.get_aggregate(self.site_id, "wifi_scan")
        by_bssid = {r["bssid"]: r for r in result}

        self.assertEqual(len(result), 3)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"]["times_seen"], 2)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"]["signal"], 75)  # latest scan's reading wins
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"]["first_seen_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:01"]["last_seen_at"], "2026-01-02T00:00:00+00:00")
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:02"]["times_seen"], 1)
        self.assertEqual(by_bssid["AA:BB:CC:DD:EE:03"]["times_seen"], 1)

    def test_sorted_strongest_first(self):
        self._write_scan("scan1", "wifi_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"ssid": "Weak", "bssid": "AA:BB:CC:DD:EE:01", "signal": 20},
            {"ssid": "Strong", "bssid": "AA:BB:CC:DD:EE:02", "signal": 90},
        ])
        result = scans.get_aggregate(self.site_id, "wifi_scan")
        self.assertEqual([r["ssid"] for r in result], ["Strong", "Weak"])

    def test_excludes_non_done_scans(self):
        self._write_scan("scan1", "wifi_scan", "running", "2026-01-01T00:00:00+00:00", [
            {"ssid": "InProgress", "bssid": "AA:BB:CC:DD:EE:01", "signal": 50},
        ])
        self._write_scan("scan2", "wifi_scan", "error", "2026-01-01T00:00:00+00:00", [
            {"ssid": "Failed", "bssid": "AA:BB:CC:DD:EE:02", "signal": 50},
        ])
        self.assertEqual(scans.get_aggregate(self.site_id, "wifi_scan"), [])

    def test_excludes_other_scan_types(self):
        self._write_scan("scan1", "bluetooth_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"address": "AA:BB:CC:DD:EE:01", "name": "Headphones", "rssi": -50},
        ])
        self.assertEqual(scans.get_aggregate(self.site_id, "wifi_scan"), [])

    def test_bluetooth_merges_by_address(self):
        self._write_scan("scan1", "bluetooth_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"address": "AA:BB:CC:DD:EE:01", "name": "Headphones", "rssi": -70},
        ])
        self._write_scan("scan2", "bluetooth_scan", "done", "2026-01-02T00:00:00+00:00", [
            {"address": "AA:BB:CC:DD:EE:01", "name": "Headphones", "rssi": -40},
        ])
        result = scans.get_aggregate(self.site_id, "bluetooth_scan")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["times_seen"], 2)
        self.assertEqual(result[0]["rssi"], -40)

    def test_unsupported_scan_type_raises(self):
        with self.assertRaises(ValueError):
            scans.get_aggregate(self.site_id, "router_screenshot")

    def test_no_scans_returns_empty_list(self):
        self.assertEqual(scans.get_aggregate("nonexistent-site", "wifi_scan"), [])


if __name__ == "__main__":
    unittest.main()
