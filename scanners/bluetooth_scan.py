#!/usr/bin/env python3
"""Standalone Bluetooth LE scanner via bleak (BlueZ D-Bus backend on Linux). No Scrapy/Playwright
dependency, so it lives outside crawler/ — same rationale as wifi_scan.py.

A single `BleakScanner.discover(timeout=..., return_adv=True)` call already scans continuously
for the given duration and accumulates every device seen, unlike nmcli (which only reports
whatever it already knows unless re-invoked) — so there's no repeat-loop here the way
wifi_scan.py needs one.

Can be run standalone for testing:
`python3 scanners/bluetooth_scan.py --scan-dir /tmp/x --duration 15`
"""
import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanners.bluetooth_parse import normalize_device  # noqa: E402

CSV_FIELDNAMES = ["address", "name", "rssi", "manufacturer_ids", "service_uuids"]


async def scan(duration, adapter=None):
    from bleak import BleakScanner

    kwargs = {"timeout": duration, "return_adv": True}
    if adapter:
        kwargs["adapter"] = adapter
    discovered = await BleakScanner.discover(**kwargs)

    devices = []
    for address, (device, adv) in discovered.items():
        devices.append(normalize_device(
            address=address,
            name=adv.local_name or device.name,
            rssi=adv.rssi,
            manufacturer_ids=adv.manufacturer_data.keys(),
            service_uuids=adv.service_uuids,
        ))

    return sorted(
        devices,
        key=lambda d: (d["rssi"] is None, -(d["rssi"] if d["rssi"] is not None else -999)),
    )


def write_outputs(scan_dir, devices):
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / "manifest.json").write_text(json.dumps(devices, indent=2))

    artifacts_dir = scan_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    with (artifacts_dir / "devices.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for d in devices:
            row = dict(d)
            row["manufacturer_ids"] = ";".join(d["manufacturer_ids"])
            row["service_uuids"] = ";".join(d["service_uuids"])
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Scan for nearby Bluetooth LE devices via bleak.")
    parser.add_argument("--scan-dir", required=True, type=Path)
    parser.add_argument("--duration", type=int, default=15, help="seconds to scan for (default 15)")
    parser.add_argument("--adapter", default=None, help="Bluetooth adapter name, e.g. hci0 (default: bleak's own choice)")
    args = parser.parse_args()

    devices = asyncio.run(scan(args.duration, args.adapter))
    write_outputs(args.scan_dir, devices)
    print(f"Captured {len(devices)} device(s).")


if __name__ == "__main__":
    main()
