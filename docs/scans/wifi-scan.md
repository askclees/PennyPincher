# WiFi Scan (`wifi_scan`)

Surveys nearby WiFi networks from the machine physically present at the site — no URL or
credentials needed. Implementation: `scanners/wifi_scan.py` + `scanners/nmcli_parse.py`.

## Params

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `duration` | int (seconds) | no | `15` | How long to keep rescanning for. |
| `interface` | string | no | nmcli's own choice | WiFi interface name (e.g. `wlan0`), if the machine has more than one and you need a specific one. |

## How it works

Repeatedly runs `nmcli -t -e yes -f SSID,BSSID,SIGNAL,CHAN,FREQ,SECURITY,IN-USE device wifi list`
(re-scanning each pass) roughly every 2 seconds for the configured `duration`, merging results
into a dict keyed by BSSID — so a network's reported signal reflects its most recent sighting, not
its first. This matters if you're walking around a site while the scan runs: a network's numbers
track where you were standing last, not where you started.

**Why not a single snapshot**: consumer APs don't always beacon in a way one scan catches, and a
single call also can't reflect movement during the scan.

### Terse-output parsing

nmcli's `-t` (terse) mode separates fields with `:` and escapes literal `:`/`\` in values with a
`\` prefix by default. This matters because BSSIDs (`AA:BB:CC:DD:EE:FF`) contain colons — a naive
`line.split(':')` would shatter one into six pieces. `scanners/nmcli_parse.py`'s
`split_terse_line()` handles this with a single left-to-right scan (not a regex lookbehind, which
would mis-handle an escaped-backslash immediately followed by a real delimiter).

## Requirements

`nmcli` (part of NetworkManager — already present on most desktop Linux distros). If `nmcli`
reports no WiFi adapter, or isn't installed at all, the scan fails with that message rather than
silently reporting zero networks.

This is inherently passive/read-only — listening for beacon frames can't mutate anything on any
network — so none of the router crawler's click-safety machinery is relevant here.

## Output

`manifest.json` — a list of records, sorted by signal strength descending:

```json
{
  "ssid": "HomeWifi",
  "bssid": "AA:BB:CC:DD:EE:01",
  "signal": 78,
  "channel": 6,
  "frequency": "2437 MHz",
  "security": "WPA2",
  "in_use": true,
  "last_seen_at": "2026-09-03T12:00:00+00:00"
}
```

`ssid` is `null` for a hidden network; `security` is `null` for an open one. `artifacts/networks.csv`
is the same rows, for opening in a spreadsheet.

## Results table grouping (display only)

Dual-band routers and mesh systems commonly broadcast one SSID across several access points
(different BSSID/channel each), which would otherwise read as the same network appearing multiple
times. The GUI's results table groups rows by SSID — showing the strongest AP's BSSID/signal with
a "(+N more)" note when there's more than one. This is **display-only**: `manifest.json` and
`networks.csv` keep every access point as its own row at full detail, since an unexpected extra AP
broadcasting a known SSID can itself be worth noticing (a rogue/evil-twin AP), not just clutter to
collapse away permanently. A hidden SSID is never grouped with other hidden networks (each stays
its own row, keyed by its own BSSID) since they can't be meaningfully identified as "the same"
network.

## Vendor identification

Not applied to WiFi scan results directly (SSIDs/BSSIDs of *routers* aren't especially informative
to vendor-tag — the AP itself isn't usually the thing you care about identifying). See
[Network Devices Scan](network-devices-scan.md), reachable from a network's row here, for
per-device vendor identification.

## Launching a Network Devices Scan from here

Every network row in a completed scan's results has a "Scan devices" button (hidden for rows with
no SSID — a hidden network can't be targeted this way). Clicking it starts a
[`network_devices_scan`](network-devices-scan.md) for that SSID at the same site. You need to
actually be joined to that network first — see that doc for why and what happens if you aren't.
