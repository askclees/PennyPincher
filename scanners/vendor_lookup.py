"""Local, offline vendor lookups for network and Bluetooth devices — no network access at scan
time. Both data files are bundled in scanners/data/, built ahead of time by build_vendor_db.py
(a separate maintenance script, run manually and occasionally, never as part of a scan).

This resolves *manufacturer/vendor* (e.g. "Apple, Inc.", "TP-Link Systems Inc.") reliably from a
MAC address or Bluetooth Company ID. It cannot resolve an exact *model* — that generally isn't
derivable from a MAC prefix or BLE advertisement alone without additional fingerprinting or a
cloud lookup, neither of which this does.
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# MAC OUI prefix lengths to try, longest first — IEEE registers blocks at three different sizes
# (MA-L 24-bit/6 hex chars, MA-M 28-bit/7, MA-S 36-bit/9), and a longer, more specific
# registration should win over a shorter one covering the same address range.
_OUI_PREFIX_LENGTHS = (9, 7, 6)

_oui_prefixes = None
_bluetooth_company_ids = None


def _load(filename):
    with (DATA_DIR / filename).open() as f:
        return json.load(f)


def _oui_table():
    global _oui_prefixes
    if _oui_prefixes is None:
        _oui_prefixes = _load("oui_prefixes.json")
    return _oui_prefixes


def _bluetooth_table():
    global _bluetooth_company_ids
    if _bluetooth_company_ids is None:
        _bluetooth_company_ids = _load("bluetooth_company_ids.json")
    return _bluetooth_company_ids


def lookup_mac_vendor(mac):
    """Returns the registered vendor name for a MAC address (e.g. 'aa:bb:cc:dd:ee:ff'), or None
    if its OUI prefix isn't in any of the three IEEE registries (or it's a locally-administered /
    randomized address, which by design has no registered vendor)."""
    if not mac:
        return None
    hex_digits = mac.replace(":", "").replace("-", "").upper()
    if len(hex_digits) < 6:
        return None

    # The second-least-significant bit of the first octet marks a locally administered address
    # (common for BLE privacy/randomized MACs) — these were never assigned to any vendor.
    try:
        first_octet = int(hex_digits[0:2], 16)
    except ValueError:
        return None
    if first_octet & 0b00000010:
        return None

    table = _oui_table()
    for length in _OUI_PREFIX_LENGTHS:
        prefix = hex_digits[:length]
        if len(prefix) == length and prefix in table:
            return table[prefix]
    return None


def lookup_bluetooth_vendor(company_id):
    """Returns the registered company name for a Bluetooth SIG Company Identifier (an int, or a
    numeric string), or None if it isn't in the assigned-numbers list."""
    if company_id is None:
        return None
    table = _bluetooth_table()
    return table.get(str(int(company_id)))
