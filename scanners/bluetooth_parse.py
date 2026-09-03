"""Normalizes bleak's raw BLE advertisement data into PennyPincher's device record shape. Pure
function, no bleak import needed, so this is unit-testable without a Bluetooth adapter — mirrors
nmcli_parse.py's role for the WiFi scan.
"""
from .vendor_lookup import lookup_bluetooth_vendor


def _format_manufacturer_id(company_id):
    """Bluetooth SIG Company Identifiers are conventionally shown in hex, e.g. 0x004C for Apple."""
    return f"0x{company_id:04X}"


def normalize_device(address, name, rssi, manufacturer_ids=None, service_uuids=None):
    manufacturer_ids = list(manufacturer_ids or [])

    vendor = None
    for company_id in sorted(manufacturer_ids):
        vendor = lookup_bluetooth_vendor(company_id)
        if vendor:
            break

    return {
        "address": address,
        "name": name or None,
        "rssi": rssi,
        "vendor": vendor,
        "manufacturer_ids": sorted(_format_manufacturer_id(i) for i in manufacturer_ids),
        "service_uuids": sorted(service_uuids or []),
    }
