#!/usr/bin/env python3
"""Unit tests for the local, offline vendor-lookup databases (scanners/vendor_lookup.py). Uses
the real bundled data files — these are exactly what a scan uses, so this also catches a broken
or missing data file, not just logic bugs. No network access.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners import vendor_lookup  # noqa: E402


class LookupMacVendorTests(unittest.TestCase):
    def test_known_oui_prefix_resolves(self):
        # 00:03:93 is Apple, Inc.'s original registered OUI — a real, stable, well-known value.
        self.assertEqual(vendor_lookup.lookup_mac_vendor("00:03:93:aa:bb:cc"), "Apple, Inc.")

    def test_case_and_separator_insensitive(self):
        self.assertEqual(vendor_lookup.lookup_mac_vendor("00-03-93-AA-BB-CC"), "Apple, Inc.")
        self.assertEqual(vendor_lookup.lookup_mac_vendor("000393aabbcc"), "Apple, Inc.")

    def test_unregistered_prefix_returns_none(self):
        self.assertIsNone(vendor_lookup.lookup_mac_vendor("ff:ff:ff:00:00:00"))

    def test_locally_administered_address_returns_none(self):
        # The U/L bit (bit 1 of the first octet) marks a locally-administered/randomized address
        # — these are never in a vendor registry by construction, even if the rest happens to
        # collide with a byte sequence that IS registered as a global OUI.
        self.assertIsNone(vendor_lookup.lookup_mac_vendor("02:03:93:aa:bb:cc"))

    def test_none_and_empty_input(self):
        self.assertIsNone(vendor_lookup.lookup_mac_vendor(None))
        self.assertIsNone(vendor_lookup.lookup_mac_vendor(""))

    def test_longest_prefix_wins(self):
        # First octet 0x00 has the locally-administered bit clear, unlike 0xAA used elsewhere in
        # this file, so this exercises prefix-length preference rather than tripping that check.
        fake_table = {"00BBCC": "Six Hex Corp", "00BBCCD": "Seven Hex Corp"}
        with patch.object(vendor_lookup, "_oui_prefixes", fake_table):
            self.assertEqual(vendor_lookup.lookup_mac_vendor("00:BB:CC:DD:EE:FF"), "Seven Hex Corp")


class LookupBluetoothVendorTests(unittest.TestCase):
    def test_known_company_id_resolves(self):
        # 76 (0x004C) is Apple, Inc.'s well-known Bluetooth SIG company identifier.
        self.assertEqual(vendor_lookup.lookup_bluetooth_vendor(76), "Apple, Inc.")

    def test_numeric_string_also_works(self):
        self.assertEqual(vendor_lookup.lookup_bluetooth_vendor("76"), "Apple, Inc.")

    def test_unknown_id_returns_none(self):
        self.assertIsNone(vendor_lookup.lookup_bluetooth_vendor(999999))

    def test_none_input(self):
        self.assertIsNone(vendor_lookup.lookup_bluetooth_vendor(None))


if __name__ == "__main__":
    unittest.main()
