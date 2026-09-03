# Network Devices Scan (`network_devices_scan`)

Discovers devices actually present on one specific WiFi network — as opposed to
[WiFi Scan](wifi-scan.md), which just detects which networks are *visible*. Implementation:
`scanners/lan_devices_scan.py` + `scanners/lan_devices_parse.py`.

**Not a directly-selectable scan type in the New Scan form.** It only makes sense once you know
which SSID to target (and are actually connected to it), so it's launched from a "Scan devices"
button on a specific network's row in a completed [WiFi Scan](wifi-scan.md)'s results table
instead. `backend/runners/__init__.py`'s `RUNNERS` registry still has it like any other scan type
— it's simply absent from `SCAN_TYPES` in `frontend/app.js`, which is what controls the dropdown.

## Params

| Param | Type | Required | Default | Description |
|---|---|---|---|---|
| `ssid` | string | yes | — | The network to scan devices on. The scan verifies you're actually connected to this exact SSID before doing anything else. |
| `interface` | string | no | auto-detected | WiFi interface name, if you need to override which connected WiFi device is used. |
| `bssid` | string | no | — | Sent by the "Scan devices" button (the target network's strongest AP) but currently unused by the runner — reserved for a future stricter check (matching the specific AP, not just the SSID) rather than doing anything today. |

## How it works

1. **Verify you're connected to the right network.** Reads which WiFi device is currently
   connected (`nmcli device status`) and which SSID it's actually joined to
   (`nmcli device wifi list`, the row marked in-use). If that doesn't match the requested `ssid`,
   the scan fails immediately with a clear error rather than silently scanning whatever network
   you happen to be on. **You have to physically join the target network yourself first** — this
   tool has no way to do that for you, and by design won't guess.
2. **Determine the subnet.** Reads the connected interface's own IPv4 address + prefix
   (`nmcli device show`, `IP4.ADDRESS`) and computes every usable host address in that subnet
   (excluding network/broadcast addresses and its own address).
3. **Ping sweep.** Pings every candidate address once, concurrently (up to 64 at a time), purely
   to populate the kernel's ARP/neighbor cache — not to check who answers ICMP. A host that
   blocks ICMP is still discovered: resolving a destination's MAC via ARP is a prerequisite of the
   kernel even attempting local-segment IP delivery, so simply *trying* to reach an address
   triggers ARP resolution regardless of whether the ping itself gets a reply.
4. **Read the neighbor table.** `ip -4 neighbor show dev <interface>`, keeping entries with a
   resolved link-layer address whose state isn't `FAILED`/`INCOMPLETE`.
5. **Reverse DNS**, best-effort, concurrently, for every discovered IP (1-second timeout each).

No root or raw sockets needed anywhere in this — unlike `arp-scan`'s or `nmap`'s ARP-scan mode,
which both require elevated privileges for raw packet crafting.

**Safety cap**: refuses to scan a subnet larger than 2048 host addresses (comfortably above a
`/22`, well short of a `/16`) rather than attempting an extremely slow sweep.

## Requirements

`nmcli` (same as [WiFi Scan](wifi-scan.md)) plus `ip` (iproute2, present on effectively every
Linux system) and unprivileged `ping`.

Passive/read-only in the same sense as the other scanners: nothing here can mutate a discovered
device, it only pings and reads the local ARP cache.

## Output

`manifest.json` — a list of records, sorted by IP address:

```json
{
  "ip": "192.168.1.42",
  "mac": "aa:bb:cc:dd:ee:ff",
  "hostname": "printer.local",
  "vendor": "Hewlett Packard"
}
```

`hostname` is `null` if reverse DNS didn't resolve (works when a router's DHCP integrates with
local DNS, which many consumer routers do; otherwise left blank). `artifacts/devices.csv` is the
same rows.

## Vendor identification

`vendor` is resolved entirely offline from the MAC's OUI prefix — see
[Vendor lookup](../vendor-lookup.md). A locally-administered/randomized MAC address is correctly
reported as `null` rather than guessed, since by definition no vendor ever registered it.

## Troubleshooting

- **"Not currently connected to any WiFi network"**: connect to the target network first, then
  retry the scan (or re-click "Scan devices" from the WiFi Scan results).
- **"Currently connected to X, not Y"**: you're on a different network than the one you clicked —
  join the right one first.
- **Fewer devices than expected**: some devices sleep/power-save their WiFi radio and may not
  respond to the ping sweep during the scan's window; re-running sometimes finds more.
