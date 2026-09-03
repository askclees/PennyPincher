# PennyPincher documentation

Detailed, per-feature reference. If you just want to get running, see the main
[README](../README.md) first — this folder goes deeper on each scan type's options and internals.

## Scan types

- [Router Screenshot](scans/router-screenshot.md) — logs into a router admin UI and screenshots
  every settings page it can reach, including ones hidden behind onClick nav buttons.
- [WiFi Scan](scans/wifi-scan.md) — nearby WiFi networks, signal/channel/security, via `nmcli`.
- [Bluetooth Scan](scans/bluetooth-scan.md) — nearby BLE devices via `bleak`/BlueZ.
- [Network Devices Scan](scans/network-devices-scan.md) — devices actually on one specific WiFi
  network, launched from a WiFi Scan's results.

## Other reference docs

- [Vendor lookup](vendor-lookup.md) — the offline MAC/Bluetooth manufacturer database used by the
  Bluetooth and Network Devices scans.
- [Site reports](reports.md) — a standalone HTML or Markdown summary of everything found at a
  site, for sharing or filing outside the app.
- [Architecture](architecture.md) — the Sites → Scans data model, the `ScanRunner` plugin
  interface, and how to add a new scan type.
- [API reference](api-reference.md) — the REST endpoints the frontend (and anything else) talks
  to, with example requests.

## Conventions used across these docs

- **Params** tables list what a scan type accepts in its `POST /sites/{id}/scans` request body's
  `params` object (same fields the GUI's New Scan form collects) — see
  [API reference](api-reference.md) for the request shape itself.
- Every scan type is Linux-only, by design — see the main README's top section for why.
- No scan type other than `router_screenshot` needs credentials; none of them ever send anything
  to a third party over the network at scan time. The one exception, called out where relevant,
  is a manually-run *maintenance* script (`scanners/build_vendor_db.py`) that refreshes bundled
  reference data — never invoked by a scan.
