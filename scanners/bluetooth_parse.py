"""Normalizes bleak's raw BLE advertisement data into PennyPincher's device record shape. Pure
function, no bleak import needed, so this is unit-testable without a Bluetooth adapter — mirrors
nmcli_parse.py's role for the WiFi scan.
"""


def _format_manufacturer_id(company_id):
    """Bluetooth SIG Company Identifiers are conventionally shown in hex, e.g. 0x004C for Apple."""
    return f"0x{company_id:04X}"


def normalize_device(address, name, rssi, manufacturer_ids=None, service_uuids=None):
    return {
        "address": address,
        "name": name or None,
        "rssi": rssi,
        "manufacturer_ids": sorted(_format_manufacturer_id(i) for i in (manufacturer_ids or [])),
        "service_uuids": sorted(service_uuids or []),
    }
