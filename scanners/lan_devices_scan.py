#!/usr/bin/env python3
"""Standalone LAN device discovery scanner. Given a WiFi network's SSID (as picked from a prior
wifi_scan's results, via the "Scan devices" button on that scan's results table), verifies the
current machine is actually connected to that network, then discovers other devices on its local
subnet.

Discovery technique: ping every candidate host address once (concurrently) to populate the
kernel's ARP/neighbor cache, then read it back via `ip neighbor show`. This finds hosts even if
they don't respond to ICMP themselves — ARP resolution is a prerequisite of any local-segment IP
delivery, so attempting to reach an address at all triggers it regardless of whether the target
answers pings. No root/raw sockets needed (unlike arp-scan/nmap's ARP scan mode), and no extra
system packages beyond what wifi_scan already requires (`nmcli`) plus the `ip` command (iproute2,
already present on effectively every Linux system).

No Scrapy/Playwright dependency, lives outside crawler/ like the other scanners.

Can be run standalone for testing:
`python3 scanners/lan_devices_scan.py --scan-dir /tmp/x --ssid "My WiFi"`
"""
import argparse
import asyncio
import csv
import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanners.lan_devices_parse import (  # noqa: E402
    find_connected_wifi_device,
    hosts_in_subnet,
    normalize_device,
    parse_active_wifi,
    parse_ip_neighbor_output,
)

MAX_HOSTS = 2048  # safety cap — bigger than a /22 (this tool's own dev network), well short of a /16
PING_CONCURRENCY = 64
DNS_TIMEOUT_SECONDS = 1
CSV_FIELDNAMES = ["ip", "mac", "vendor", "hostname"]


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed (exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


def resolve_interface(interface):
    if interface:
        return interface
    status = run(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    device = find_connected_wifi_device(status)
    if not device:
        raise RuntimeError("Not currently connected to any WiFi network.")
    return device


def verify_connected_to(ssid):
    output = run(["nmcli", "-t", "-f", "IN-USE,SSID,BSSID", "device", "wifi", "list"])
    active = parse_active_wifi(output)
    if not active:
        raise RuntimeError("Not currently connected to any WiFi network.")
    if active["ssid"] != ssid:
        raise RuntimeError(
            f"Currently connected to {active['ssid']!r}, not {ssid!r} — "
            "join that network before scanning it."
        )


def own_address(interface):
    output = run(["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", interface])
    first_line = next((line for line in output.splitlines() if line.strip()), "")
    if ":" not in first_line:
        raise RuntimeError(f"Could not determine an IPv4 address for {interface}.")
    return first_line.split(":", 1)[1]


async def ping_sweep(hosts):
    semaphore = asyncio.Semaphore(PING_CONCURRENCY)

    async def ping_one(host):
        async with semaphore:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "1", host,
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()

    await asyncio.gather(*(ping_one(h) for h in hosts))


def _reverse_dns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return None


async def resolve_hostnames(ips):
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*(loop.run_in_executor(None, _reverse_dns, ip) for ip in ips))
    return dict(zip(ips, results))


async def scan(ssid, interface=None):
    interface = resolve_interface(interface)
    verify_connected_to(ssid)

    address = own_address(interface)
    hosts = hosts_in_subnet(address)
    if len(hosts) > MAX_HOSTS:
        raise RuntimeError(
            f"Subnet has {len(hosts)} host addresses, over this tool's {MAX_HOSTS}-host safety "
            "cap — too large to sweep."
        )

    await ping_sweep(hosts)

    neighbor_output = run(["ip", "-4", "neighbor", "show", "dev", interface])
    neighbors = parse_ip_neighbor_output(neighbor_output)

    socket.setdefaulttimeout(DNS_TIMEOUT_SECONDS)
    hostnames = await resolve_hostnames([n["ip"] for n in neighbors])

    devices = [normalize_device(n["ip"], n["mac"], hostnames.get(n["ip"])) for n in neighbors]
    devices.sort(key=lambda d: tuple(int(part) for part in d["ip"].split(".")))
    return devices


def write_outputs(scan_dir, devices):
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / "manifest.json").write_text(json.dumps(devices, indent=2))

    artifacts_dir = scan_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    with (artifacts_dir / "devices.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(devices)


def main():
    parser = argparse.ArgumentParser(
        description="Discover devices on the WiFi network you're currently connected to."
    )
    parser.add_argument("--scan-dir", required=True, type=Path)
    parser.add_argument("--ssid", required=True)
    parser.add_argument("--interface", default=None, help="WiFi interface name (default: auto-detect the connected one)")
    args = parser.parse_args()

    devices = asyncio.run(scan(args.ssid, args.interface))
    write_outputs(args.scan_dir, devices)
    print(f"Found {len(devices)} device(s) on {args.ssid!r}.")


if __name__ == "__main__":
    main()
