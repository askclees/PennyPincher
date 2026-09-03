# Bluetooth Scan (`bluetooth_scan`)

Surveys nearby Bluetooth LE devices from the machine physically present at the site. Implementation:
`scanners/bluetooth_scan.py` + `scanners/bluetooth_parse.py`, via `bleak` (BlueZ over D-Bus).

## Params

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `duration` | int (seconds) | no | `15` | How long to scan for. |
| `adapter` | string | no | bleak's own choice | Bluetooth adapter name (e.g. `hci0`), if the machine has more than one. |

## How it works

A single `BleakScanner.discover(timeout=duration, return_adv=True)` call scans continuously for
the given duration and accumulates every device seen — unlike WiFi's `nmcli`, which only reports
whatever it currently knows unless re-invoked, `bleak`'s discovery already covers the whole window
in one call. Each discovered device's advertisement data (name, RSSI, manufacturer ID(s), service
UUIDs) is normalized via `scanners/bluetooth_parse.py::normalize_device()`.

## Requirements

`bluetoothd` (BlueZ) running with a working adapter — `systemctl status bluetooth` to check. If no
adapter/daemon is reachable, the scan fails with bleak's D-Bus error rather than hanging or
silently reporting zero devices.

Passive/read-only: nothing here can mutate a discovered device, it's listening for advertisements
only.

## Output

`manifest.json` — a list of records, sorted by RSSI (signal strength) descending:

```json
{
  "address": "AA:BB:CC:DD:EE:01",
  "name": "My Headphones",
  "rssi": -52,
  "vendor": "Apple, Inc.",
  "manufacturer_ids": ["0x004C"],
  "service_uuids": ["0000180f-0000-1000-8000-00805f9b34fb"]
}
```

`name` is `null` if the device didn't advertise a local name. `manufacturer_ids` is a
(sorted, deduplicated) list of Bluetooth SIG Company Identifiers in hex — usually just one, rarely
more. `artifacts/devices.csv` is the same rows, for opening in a spreadsheet.

## Vendor identification

`vendor` is resolved entirely offline from `manufacturer_ids` — see
[Vendor lookup](../vendor-lookup.md) for how the local database works and its limits (manufacturer,
not exact model). If a device advertises multiple manufacturer IDs, they're tried in ascending
order and the first one that resolves wins.

## Master list — every device seen across all Bluetooth scans at a site

A single scan only shows what was in range during that run. The site page has an "All Bluetooth
devices seen at this site" link (once at least one `bluetooth_scan` there has completed) that
merges **every** completed Bluetooth scan at the site into one table, deduplicated by `address` —
plus First Seen, Last Seen, and Times Seen columns (see
[API reference](../api-reference.md#get-sitessite_idaggregatescan_type) for exactly how those are
computed). Useful for telling a device that's only ever passed through once from one that's
consistently present at the site.
