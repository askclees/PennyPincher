#!/usr/bin/env python3
"""Unit tests for the Bluetooth scan's device-record normalizer
(scanners/bluetooth_parse.py). No real Bluetooth adapter or bleak import needed — pure values in,
structured data out.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.bluetooth_parse import normalize_device  # noqa: E402


class NormalizeDeviceTests(unittest.TestCase):
    def test_normalizes_full_record(self):
        device = normalize_device(
            address="AA:BB:CC:DD:EE:01",
            name="My Headphones",
            rssi=-52,
            manufacturer_ids=[76],
            service_uuids=["0000180f-0000-1000-8000-00805f9b34fb"],
        )
        self.assertEqual(device["address"], "AA:BB:CC:DD:EE:01")
        self.assertEqual(device["name"], "My Headphones")
        self.assertEqual(device["rssi"], -52)
        self.assertEqual(device["manufacturer_ids"], ["0x004C"])
        self.assertEqual(device["service_uuids"], ["0000180f-0000-1000-8000-00805f9b34fb"])

    def test_unnamed_device_becomes_none(self):
        device = normalize_device(address="AA:BB:CC:DD:EE:02", name="", rssi=-70)
        self.assertIsNone(device["name"])

    def test_missing_manufacturer_and_service_data_become_empty_lists(self):
        device = normalize_device(address="AA:BB:CC:DD:EE:03", name="X", rssi=-80)
        self.assertEqual(device["manufacturer_ids"], [])
        self.assertEqual(device["service_uuids"], [])

    def test_manufacturer_ids_sorted_and_hex_formatted(self):
        device = normalize_device(
            address="AA:BB:CC:DD:EE:04", name="X", rssi=-60,
            manufacturer_ids=[6, 76],
        )
        self.assertEqual(device["manufacturer_ids"], ["0x0006", "0x004C"])

    def test_multiple_manufacturer_ids_from_dict_keys(self):
        # bleak's AdvertisementData.manufacturer_data is a dict[int, bytes] — normalize_device
        # is called with just its .keys(), which this exercises via a plain dict.
        manufacturer_data = {76: b"\x01\x02", 6: b"\x03"}
        device = normalize_device(
            address="AA:BB:CC:DD:EE:05", name="X", rssi=-60,
            manufacturer_ids=manufacturer_data.keys(),
        )
        self.assertEqual(device["manufacturer_ids"], ["0x0006", "0x004C"])


if __name__ == "__main__":
    unittest.main()
