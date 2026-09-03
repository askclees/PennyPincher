"""Parses nmcli/`ip neighbor` output for the LAN-devices scan (discovering hosts on the network
you're currently connected to, given an SSID selected from a prior wifi_scan's results). Pure
functions, no subprocess dependency, so unit-testable without real hardware — mirrors
nmcli_parse.py's role for the WiFi scan itself.
"""
import ipaddress

from .nmcli_parse import split_terse_line
from .vendor_lookup import lookup_mac_vendor

_TRUTHY = ("*", "yes", "true")


def parse_active_wifi(output):
    """Given `nmcli -t -f IN-USE,SSID,BSSID device wifi list` output, returns {"ssid": ...,
    "bssid": ...} for the row marked in-use, or None if not currently connected to any WiFi
    network."""
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = split_terse_line(line)
        if len(fields) < 3:
            continue
        in_use, ssid, bssid = fields[0], fields[1], fields[2]
        if in_use.strip().lower() in _TRUTHY:
            return {"ssid": ssid or None, "bssid": bssid or None}
    return None


def find_connected_wifi_device(output):
    """Given `nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status` output, returns the
    device name of the first connected WiFi device, or None if there isn't one."""
    for line in output.splitlines():
        if not line.strip():
            continue
        fields = split_terse_line(line)
        if len(fields) < 3:
            continue
        device, dev_type, state = fields[0], fields[1], fields[2]
        if dev_type == "wifi" and state.startswith("connected"):
            return device
    return None


def parse_ip_neighbor_output(output):
    """Given `ip -4 neighbor show dev <iface>` output, returns [{ip, mac, state}, ...] for
    entries with a resolved link-layer address, excluding FAILED/INCOMPLETE ones (no response,
    nothing actually there)."""
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        ip = parts[0]
        state = parts[-1]
        mac = parts[parts.index("lladdr") + 1] if "lladdr" in parts else None
        if not mac or state in ("FAILED", "INCOMPLETE"):
            continue
        devices.append({"ip": ip, "mac": mac, "state": state})
    return devices


def hosts_in_subnet(ip_with_prefix, exclude=()):
    """Given an interface address like '192.168.1.42/24', returns every usable host address in
    that subnet as strings — excludes the network/broadcast addresses (ipaddress.hosts() already
    does this) plus our own address and anything else in `exclude`."""
    interface = ipaddress.ip_interface(ip_with_prefix)
    skip = set(exclude) | {str(interface.ip)}
    return [str(host) for host in interface.network.hosts() if str(host) not in skip]


def normalize_device(ip, mac, hostname=None):
    return {"ip": ip, "mac": mac, "hostname": hostname or None, "vendor": lookup_mac_vendor(mac)}
