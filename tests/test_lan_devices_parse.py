#!/usr/bin/env python3
"""Unit tests for the network-devices scan's nmcli/`ip neighbor` parsers and subnet math
(scanners/lan_devices_parse.py). No real network adapter needed — pure fixtures in, structured
data out.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanners.lan_devices_parse import (  # noqa: E402
    find_connected_wifi_device,
    hosts_in_subnet,
    normalize_device,
    parse_active_wifi,
    parse_ip_neighbor_output,
)


class ParseActiveWifiTests(unittest.TestCase):
    def test_finds_row_marked_in_use(self):
        output = (
            r"no:OtherNet:AA\:BB\:CC\:DD\:EE\:01" + "\n"
            r"*:HomeWifi:AA\:BB\:CC\:DD\:EE\:02" + "\n"
        )
        self.assertEqual(
            parse_active_wifi(output),
            {"ssid": "HomeWifi", "bssid": "AA:BB:CC:DD:EE:02"},
        )

    def test_returns_none_when_not_connected(self):
        output = r"no:OtherNet:AA\:BB\:CC\:DD\:EE\:01" + "\n"
        self.assertIsNone(parse_active_wifi(output))

    def test_empty_output_returns_none(self):
        self.assertIsNone(parse_active_wifi(""))


class FindConnectedWifiDeviceTests(unittest.TestCase):
    def test_finds_connected_wifi_device(self):
        output = (
            "eth0:ethernet:connected:netplan-eth0\n"
            "wlan0:wifi:connected:HomeWifi\n"
        )
        self.assertEqual(find_connected_wifi_device(output), "wlan0")

    def test_ignores_non_wifi_devices(self):
        output = "eth0:ethernet:connected:netplan-eth0\n"
        self.assertIsNone(find_connected_wifi_device(output))

    def test_ignores_disconnected_wifi_device(self):
        output = "wlan0:wifi:disconnected:--\n"
        self.assertIsNone(find_connected_wifi_device(output))


class ParseIpNeighborOutputTests(unittest.TestCase):
    def test_parses_reachable_and_stale_entries(self):
        output = (
            "192.168.1.1 lladdr d4:d6:df:a3:64:b0 REACHABLE\n"
            "192.168.1.5 lladdr e8:ff:1e:df:e2:81 STALE\n"
        )
        devices = parse_ip_neighbor_output(output)
        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0], {"ip": "192.168.1.1", "mac": "d4:d6:df:a3:64:b0", "state": "REACHABLE"})

    def test_excludes_failed_and_incomplete(self):
        output = (
            "192.168.1.9 dev eth0  FAILED\n"
            "192.168.1.10 dev eth0  INCOMPLETE\n"
        )
        self.assertEqual(parse_ip_neighbor_output(output), [])

    def test_excludes_entries_without_lladdr(self):
        output = "192.168.1.9 dev eth0  STALE\n"
        self.assertEqual(parse_ip_neighbor_output(output), [])

    def test_empty_output(self):
        self.assertEqual(parse_ip_neighbor_output(""), [])


class HostsInSubnetTests(unittest.TestCase):
    def test_slash_24_excludes_network_broadcast_and_self(self):
        hosts = hosts_in_subnet("192.168.1.42/24")
        self.assertEqual(len(hosts), 253)  # 254 usable minus our own address
        self.assertNotIn("192.168.1.0", hosts)
        self.assertNotIn("192.168.1.255", hosts)
        self.assertNotIn("192.168.1.42", hosts)
        self.assertIn("192.168.1.1", hosts)

    def test_extra_exclude_list_honored(self):
        hosts = hosts_in_subnet("10.0.0.1/29", exclude=["10.0.0.2"])
        self.assertNotIn("10.0.0.2", hosts)
        self.assertNotIn("10.0.0.1", hosts)


class NormalizeDeviceTests(unittest.TestCase):
    def test_normalizes(self):
        device = normalize_device("192.168.1.5", "aa:bb:cc:dd:ee:ff", "printer.local")
        self.assertEqual(device, {"ip": "192.168.1.5", "mac": "aa:bb:cc:dd:ee:ff", "hostname": "printer.local"})

    def test_missing_hostname_becomes_none(self):
        device = normalize_device("192.168.1.5", "aa:bb:cc:dd:ee:ff")
        self.assertIsNone(device["hostname"])


if __name__ == "__main__":
    unittest.main()
