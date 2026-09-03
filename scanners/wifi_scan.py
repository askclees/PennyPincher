#!/usr/bin/env python3
"""Standalone WiFi network scanner (Linux, via nmcli). No Scrapy/Playwright dependency — this is
just repeated `nmcli` calls, so it lives outside crawler/ rather than being shoehorned into that
Scrapy project.

Repeatedly scans for the configured duration, de-duplicating by BSSID and keeping each network's
most recent reading (a network's signal reflects its latest, not first, sighting — useful if
walking around a site while it runs), then writes manifest.json (PennyPincher's generic scan
results format) plus a networks.csv convenience copy into the scan's artifacts/ dir.

Can be run standalone for testing: `python3 scanners/wifi_scan.py --scan-dir /tmp/x --duration 15`
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanners.nmcli_parse import FIELDS, normalize_network, parse_wifi_list_output  # noqa: E402

SCAN_INTERVAL_SECONDS = 2
CSV_FIELDNAMES = ["ssid", "bssid", "signal", "channel", "frequency", "security", "in_use", "last_seen_at"]


def run_nmcli(interface=None):
    cmd = ["nmcli", "-t", "-e", "yes", "-f", ",".join(FIELDS), "device", "wifi", "list"]
    if interface:
        cmd += ["ifname", interface]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"nmcli failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def scan(duration, interface=None):
    networks = {}  # bssid -> normalized dict, most recent sighting wins
    deadline = time.monotonic() + duration
    while True:
        output = run_nmcli(interface)
        now = datetime.now(timezone.utc).isoformat()
        for row in parse_wifi_list_output(output):
            network = normalize_network(row)
            bssid = network.get("bssid")
            if not bssid:
                continue
            network["last_seen_at"] = now
            networks[bssid] = network

        if time.monotonic() >= deadline:
            break
        time.sleep(SCAN_INTERVAL_SECONDS)

    return sorted(
        networks.values(),
        key=lambda n: (n["signal"] is None, -(n["signal"] or 0)),
    )


def write_outputs(scan_dir, networks):
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / "manifest.json").write_text(json.dumps(networks, indent=2))

    artifacts_dir = scan_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    with (artifacts_dir / "networks.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(networks)


def main():
    parser = argparse.ArgumentParser(description="Scan for nearby WiFi networks via nmcli.")
    parser.add_argument("--scan-dir", required=True, type=Path)
    parser.add_argument("--duration", type=int, default=15, help="seconds to scan for (default 15)")
    parser.add_argument("--interface", default=None, help="WiFi interface name (default: nmcli's own choice)")
    args = parser.parse_args()

    networks = scan(args.duration, args.interface)
    write_outputs(args.scan_dir, networks)
    print(f"Captured {len(networks)} network(s).")


if __name__ == "__main__":
    main()
