#!/usr/bin/env python3
"""Unit tests for the WiFi scan's nmcli terse-output parser
(scanners/nmcli_parse.py). No real WiFi adapter or root needed — pure string fixtures in,
structured data out.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.nmcli_parse import (  # noqa: E402
    FIELDS,
    normalize_network,
    parse_wifi_list_output,
    split_terse_line,
)


class SplitTerseLineTests(unittest.TestCase):
    def test_splits_plain_fields(self):
        self.assertEqual(split_terse_line("HomeNet:6:WPA2"), ["HomeNet", "6", "WPA2"])

    def test_unescapes_colon_inside_bssid(self):
        # A BSSID's colons are escaped by nmcli's terse mode (`-e yes`, the default) since `:` is
        # the field separator — the parser must not shatter it into six pieces.
        line = r"HomeNet\:AA\:BB\:CC\:DD\:EE\:FF:6"
        self.assertEqual(split_terse_line(line), ["HomeNet:AA:BB:CC:DD:EE:FF", "6"])

    def test_unescapes_literal_backslash(self):
        line = r"Weird\\Name:6"
        self.assertEqual(split_terse_line(line), ["Weird\\Name", "6"])

    def test_empty_fields_preserved(self):
        self.assertEqual(split_terse_line("::6"), ["", "", "6"])


class ParseWifiListOutputTests(unittest.TestCase):
    def test_parses_multiple_lines_into_field_dicts(self):
        output = (
            r"HomeNet:AA\:BB\:CC\:DD\:EE\:01:78:6:2437 MHz:WPA2:" + "\n"
            r"CafeGuest:AA\:BB\:CC\:DD\:EE\:02:44:11:2462 MHz:--:*" + "\n"
        )
        rows = parse_wifi_list_output(output)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["SSID"], "HomeNet")
        self.assertEqual(rows[0]["BSSID"], "AA:BB:CC:DD:EE:01")
        self.assertEqual(rows[1]["IN-USE"], "*")

    def test_skips_blank_lines(self):
        output = "HomeNet:AA\\:BB\\:CC\\:DD\\:EE\\:01:78:6:2437 MHz:WPA2:\n\n"
        rows = parse_wifi_list_output(output)
        self.assertEqual(len(rows), 1)

    def test_uses_default_fields_length(self):
        self.assertEqual(len(FIELDS), 7)


class NormalizeNetworkTests(unittest.TestCase):
    def test_normalizes_full_row(self):
        row = {
            "SSID": "HomeNet",
            "BSSID": "AA:BB:CC:DD:EE:01",
            "SIGNAL": "78",
            "CHAN": "6",
            "FREQ": "2437 MHz",
            "SECURITY": "WPA2",
            "IN-USE": "*",
        }
        network = normalize_network(row)
        self.assertEqual(network["ssid"], "HomeNet")
        self.assertEqual(network["bssid"], "AA:BB:CC:DD:EE:01")
        self.assertEqual(network["signal"], 78)
        self.assertEqual(network["channel"], 6)
        self.assertEqual(network["frequency"], "2437 MHz")
        self.assertEqual(network["security"], "WPA2")
        self.assertTrue(network["in_use"])

    def test_hidden_ssid_and_open_security_become_none(self):
        row = {"SSID": "", "BSSID": "AA:BB:CC:DD:EE:02", "SIGNAL": "40", "CHAN": "1",
               "FREQ": "2412 MHz", "SECURITY": "", "IN-USE": ""}
        network = normalize_network(row)
        self.assertIsNone(network["ssid"])
        self.assertIsNone(network["security"])
        self.assertFalse(network["in_use"])

    def test_non_numeric_signal_becomes_none(self):
        row = {"SSID": "X", "BSSID": "AA:BB:CC:DD:EE:03", "SIGNAL": "", "CHAN": "",
               "FREQ": "", "SECURITY": "", "IN-USE": ""}
        network = normalize_network(row)
        self.assertIsNone(network["signal"])
        self.assertIsNone(network["channel"])


if __name__ == "__main__":
    unittest.main()
