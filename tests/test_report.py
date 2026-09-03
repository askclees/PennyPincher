#!/usr/bin/env python3
"""Tests for backend/report.py — the HTML/Markdown site report generators. Runs against a
temporary data directory, building fake site.json/status.json/manifest.json files directly.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.report as report  # noqa: E402
import backend.scans as scans  # noqa: E402
import backend.sites as sites  # noqa: E402


class ReportTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_sites_data_dir = sites.DATA_DIR
        self._original_scans_sites_dir = scans.SITES_DIR
        tmp_path = Path(self._tmpdir.name)
        sites.DATA_DIR = tmp_path
        scans.SITES_DIR = tmp_path

    def tearDown(self):
        sites.DATA_DIR = self._original_sites_data_dir
        scans.SITES_DIR = self._original_scans_sites_dir
        self._tmpdir.cleanup()

    def _make_site(self, address="123 Main St", notes=None):
        return sites.get_or_create_site(address, notes)

    def _write_scan(self, site_id, scan_id, scan_type, status, started_at, manifest,
                     artifacts=None):
        scan_dir = scans.SITES_DIR / site_id / "scans" / scan_id
        artifacts_dir = scan_dir / "artifacts"
        artifacts_dir.mkdir(parents=True)
        (scan_dir / "status.json").write_text(json.dumps({
            "scan_type": scan_type, "status": status, "started_at": started_at,
        }))
        (scan_dir / "manifest.json").write_text(json.dumps(manifest))
        for name, content in (artifacts or {}).items():
            (artifacts_dir / name).write_bytes(content)

    def test_missing_site_raises(self):
        with self.assertRaises(ValueError):
            report.generate_html_report("nonexistent")
        with self.assertRaises(ValueError):
            report.generate_markdown_report("nonexistent")

    def test_html_report_with_no_scans_yet(self):
        site_id = self._make_site("1 Empty St")
        html = report.generate_html_report(site_id)
        self.assertIn("1 Empty St", html)
        self.assertIn("No completed router screenshot scan yet.", html)
        self.assertIn("WiFi Networks (0)", html)
        self.assertIn("Bluetooth Devices (0)", html)
        self.assertIn("Network Devices (0)", html)

    def test_html_report_embeds_screenshot_as_base64(self):
        site_id = self._make_site("2 Router Rd")
        fake_png = b"\x89PNG\r\n\x1a\n" + b"fake-image-bytes"
        self._write_scan(
            site_id, "scan1", "router_screenshot", "done", "2026-01-01T00:00:00+00:00",
            [{"url": "https://192.168.1.1/", "screenshot_file": "page_0001.png", "title": "Status"}],
            artifacts={"page_0001.png": fake_png},
        )
        html = report.generate_html_report(site_id)
        self.assertIn("Status", html)
        self.assertIn("https://192.168.1.1/", html)
        self.assertIn("data:image/png;base64,", html)
        import base64
        self.assertIn(base64.b64encode(fake_png).decode("ascii"), html)
        # The lightbox is what makes those base64-embedded thumbnails actually viewable at full
        # size — it's otherwise easy to forget to wire up since it's pure client-side JS with no
        # server-side rendering to catch a typo in the id it hooks onto.
        self.assertIn('id="lightbox-overlay"', html)
        self.assertIn('querySelectorAll(".gallery img")', html)

    def test_no_lightbox_markup_when_no_screenshots(self):
        site_id = self._make_site("2b No Screenshots Ln")
        html = report.generate_html_report(site_id)
        self.assertNotIn("lightbox-overlay", html)

    def test_html_escapes_untrusted_looking_content(self):
        site_id = self._make_site("3 XSS Ave", notes="<script>alert(1)</script>")
        html = report.generate_html_report(site_id)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_master_lists_use_aggregate_data(self):
        site_id = self._make_site("4 Wifi Way")
        self._write_scan(site_id, "scan1", "wifi_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"ssid": "HomeWifi", "bssid": "AA:BB:CC:DD:EE:01", "signal": 60},
        ])
        self._write_scan(site_id, "scan2", "wifi_scan", "done", "2026-01-02T00:00:00+00:00", [
            {"ssid": "HomeWifi", "bssid": "AA:BB:CC:DD:EE:01", "signal": 80},
        ])
        html = report.generate_html_report(site_id)
        md = report.generate_markdown_report(site_id)
        for text in (html, md):
            self.assertIn("HomeWifi", text)
            self.assertIn("WiFi Networks (1)", text)  # deduplicated to 1 network, not 2 rows

    def test_markdown_report_basic_shape(self):
        site_id = self._make_site("5 Markdown Blvd")
        self._write_scan(
            site_id, "scan1", "router_screenshot", "done", "2026-01-01T00:00:00+00:00",
            [{"url": "https://192.168.1.1/", "screenshot_file": "page_0001.png", "title": "Home"}],
        )
        md = report.generate_markdown_report(site_id)
        self.assertTrue(md.startswith("# 5 Markdown Blvd"))
        self.assertIn("## Router Screenshots", md)
        self.assertIn("| 1 | Home | https://192.168.1.1/ |", md)
        self.assertNotIn("data:image", md)  # markdown report never embeds images

    def test_markdown_table_escapes_pipe_characters(self):
        site_id = self._make_site("6 Pipe St")
        self._write_scan(site_id, "scan1", "bluetooth_scan", "done", "2026-01-01T00:00:00+00:00", [
            {"address": "AA:BB:CC:DD:EE:01", "name": "Weird|Name", "rssi": -50},
        ])
        md = report.generate_markdown_report(site_id)
        self.assertIn("Weird\\|Name", md)


if __name__ == "__main__":
    unittest.main()
