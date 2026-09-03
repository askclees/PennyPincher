#!/usr/bin/env python3
"""Regression test for a real bug: each scanner script's CSV_FIELDNAMES must exactly match the
keys its normalize_*() function actually returns, or csv.DictWriter raises ValueError (default
extrasaction="raise") on the first row — after manifest.json has already been written
successfully, so a scan reports real results yet still exits non-zero and shows as "error".

This happened twice in practice: bluetooth_scan.py and lan_devices_scan.py both had their
normalize_device() gain a "vendor" key (when offline vendor lookup was added) without their
CSV_FIELDNAMES being updated to match. This test would have caught both immediately.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners import bluetooth_scan, lan_devices_scan, wifi_scan  # noqa: E402
from scanners.bluetooth_parse import normalize_device as normalize_bluetooth  # noqa: E402
from scanners.lan_devices_parse import normalize_device as normalize_lan_device  # noqa: E402
from scanners.nmcli_parse import normalize_network  # noqa: E402


class CsvFieldnamesMatchNormalizedKeysTests(unittest.TestCase):
    def test_wifi_scan_csv_fieldnames(self):
        row = {"SSID": "X", "BSSID": "AA:BB:CC:DD:EE:01", "SIGNAL": "50", "CHAN": "6",
               "FREQ": "2437 MHz", "SECURITY": "WPA2", "IN-USE": ""}
        network = normalize_network(row)
        network["last_seen_at"] = "2026-01-01T00:00:00+00:00"  # added by wifi_scan.scan()
        self.assertEqual(set(wifi_scan.CSV_FIELDNAMES), set(network.keys()))

    def test_bluetooth_scan_csv_fieldnames(self):
        device = normalize_bluetooth("AA:BB:CC:DD:EE:01", "X", -50, manufacturer_ids=[76])
        self.assertEqual(set(bluetooth_scan.CSV_FIELDNAMES), set(device.keys()))

    def test_lan_devices_scan_csv_fieldnames(self):
        device = normalize_lan_device("192.168.1.5", "aa:bb:cc:dd:ee:ff", "host.local")
        self.assertEqual(set(lan_devices_scan.CSV_FIELDNAMES), set(device.keys()))


if __name__ == "__main__":
    unittest.main()
