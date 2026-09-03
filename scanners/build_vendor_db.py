#!/usr/bin/env python3
"""Maintenance script: rebuilds the local vendor-lookup databases in scanners/data/ from the
official public sources. NOT run as part of any scan — vendor_lookup.py only ever reads the
already-built JSON files bundled in this repo, so normal scanning never touches the network for
this. Run this manually, occasionally, if you want fresher vendor data:

    python3 scanners/build_vendor_db.py

Sources:
- IEEE's own registries for MAC OUI prefixes (all three: MA-L/24-bit, MA-M/28-bit, MA-S/36-bit —
  merging all three, keyed by prefix length, gives longest-prefix-match semantics for free at
  lookup time).
- Nordic Semiconductor's bluetooth-numbers-database (BSD-3-Clause), a convenience mirror of the
  Bluetooth SIG's official company identifiers assigned-numbers list.
"""
import csv
import io
import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

OUI_SOURCES = [
    "https://standards-oui.ieee.org/oui/oui.csv",       # MA-L, 24-bit (6 hex chars)
    "https://standards-oui.ieee.org/oui28/mam.csv",     # MA-M, 28-bit (7 hex chars)
    "https://standards-oui.ieee.org/oui36/oui36.csv",   # MA-S, 36-bit (9 hex chars)
]
BLUETOOTH_COMPANY_IDS_SOURCE = (
    "https://raw.githubusercontent.com/NordicSemiconductor/"
    "bluetooth-numbers-database/master/v1/company_ids.json"
)


def _fetch(url):
    # IEEE's CDN rejects urllib's default User-Agent outright (HTTP 418) — anything plausible
    # works, this isn't an attempt to disguise the request as a browser for any other reason.
    request = urllib.request.Request(url, headers={"User-Agent": "PennyPincher-vendor-db-updater/1.0"})
    with urllib.request.urlopen(request, timeout=30) as resp:
        return resp.read().decode("utf-8-sig")


def build_oui_prefixes():
    combined = {}
    for url in OUI_SOURCES:
        reader = csv.DictReader(io.StringIO(_fetch(url)))
        for row in reader:
            prefix = row["Assignment"].strip().upper()
            name = row["Organization Name"].strip()
            if prefix and name:
                combined[prefix] = name
    return combined


def build_bluetooth_company_ids():
    entries = json.loads(_fetch(BLUETOOTH_COMPANY_IDS_SOURCE))
    return {str(entry["code"]): entry["name"] for entry in entries}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    oui_prefixes = build_oui_prefixes()
    (DATA_DIR / "oui_prefixes.json").write_text(
        json.dumps(oui_prefixes, separators=(",", ":"), sort_keys=True)
    )
    print(f"Wrote {len(oui_prefixes)} MAC OUI prefixes.")

    company_ids = build_bluetooth_company_ids()
    (DATA_DIR / "bluetooth_company_ids.json").write_text(
        json.dumps(company_ids, separators=(",", ":"), sort_keys=True)
    )
    print(f"Wrote {len(company_ids)} Bluetooth company IDs.")


if __name__ == "__main__":
    main()
