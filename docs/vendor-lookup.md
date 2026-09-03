# Vendor lookup (offline)

Resolves a device's **manufacturer** — not exact model — from a MAC address or Bluetooth Company
ID, using two databases bundled locally in `scanners/data/`. Implementation:
`scanners/vendor_lookup.py`.

**No network access at scan time, ever.** Both data files are pre-built; a scan only ever reads
them from disk. The only thing in this whole repo that touches the network for this feature is a
separate, manually-run maintenance script (see [Refreshing the data](#refreshing-the-data)) — it
is never invoked automatically or as part of any scan.

## What it resolves, and what it can't

| | Can resolve | Cannot resolve |
|---|---|---|
| MAC address (`network_devices_scan`) | Manufacturer, e.g. `"TP-Link Systems Inc."` | Exact model, e.g. `"Archer AX55"` |
| Bluetooth Company ID (`bluetooth_scan`) | Manufacturer, e.g. `"Apple, Inc."` | Exact model, e.g. `"iPhone 14 Pro"` |

Getting to a specific model reliably generally needs either a cloud fingerprint database or
protocol-level fingerprinting (DHCP options, mDNS records, BLE GATT services) — meaningfully
harder problems than a static lookup table, and not implemented here.

## MAC address lookup (`lookup_mac_vendor`)

1. **Locally-administered check first.** The second-least-significant bit of the first octet (the
   "U/L bit") marks a locally-administered or randomized address — common for BLE privacy
   addresses and some OS MAC-randomization features. These were never assigned to any vendor by
   construction, so this returns `None` immediately rather than risking a coincidental false match
   against the registry.
2. **Longest-prefix match.** IEEE registers OUI blocks at three different sizes — MA-L (24-bit / 6
   hex chars, the classic case), MA-M (28-bit / 7 hex chars), and MA-S (36-bit / 9 hex chars). All
   three registries are merged into one table; a lookup tries 9, then 7, then 6 hex-char prefixes
   in that order, so a more specific registration correctly takes precedence over a shorter one
   that happens to cover the same address range.

## Bluetooth Company ID lookup (`lookup_bluetooth_vendor`)

A direct lookup — the ID from the device's advertisement (an int, e.g. `76` for Apple, Inc.)
against the Bluetooth SIG's assigned-numbers table. Accepts either an int or a numeric string.

## The bundled data files

| File | Entries | Source |
|---|---|---|
| `scanners/data/oui_prefixes.json` | ~53,800 | IEEE's own MA-L/MA-M/MA-S OUI registries (`standards-oui.ieee.org`) |
| `scanners/data/bluetooth_company_ids.json` | ~4,000 | Bluetooth SIG company identifiers, via [Nordic Semiconductor's `bluetooth-numbers-database`](https://github.com/NordicSemiconductor/bluetooth-numbers-database) (BSD-3-Clause), a convenience mirror of the SIG's official list |

Both are flat JSON objects (`{prefix_or_id: vendor_name}`), loaded once and cached in memory for
the life of the scan process.

## Refreshing the data

New OUI/company-ID assignments happen continuously, so these files are stale from the moment
they're built. To refresh them:

```
python3 scanners/build_vendor_db.py
```

This re-fetches from the same official sources and overwrites both files in place. Run it
occasionally, whenever you want — it's a manual step, not part of `pip install` or any scan.

(Implementation note: IEEE's CDN rejects `urllib`'s default User-Agent with an HTTP 418 — the
script sends a descriptive one, `PennyPincher-vendor-db-updater/1.0`, purely to get past that, not
to disguise the request.)

## Testing

`tests/test_vendor_lookup.py` runs against the real bundled data files (so it also catches a
broken/missing file, not just logic bugs), using well-known stable values — Apple, Inc.'s original
`00:03:93` OUI and Bluetooth Company ID `76` — plus the locally-administered-address exclusion and
longest-prefix-match preference (the latter via a small mocked table, since finding two real
overlapping-but-different-length registrations to assert against isn't practical).
