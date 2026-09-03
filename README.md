# PennyPincher

Logs into a router's web admin UI, crawls every settings page it can reach via on-page links, and
screenshots each one — organized by the physical **site** (address) it was captured at, since the
same tool gets run at multiple locations. A web frontend lets you enter an address, kick off a
capture with live credentials (never stored to disk), watch it run, browse the resulting
screenshots (each captioned with the URL it came from), and export everything as a zip.

Router screenshotting is one of four **scan types** available at a site — `wifi_scan` (nearby WiFi
networks), `bluetooth_scan` (nearby BLE devices), and `network_devices_scan` (devices actually on
one specific WiFi network, picked from a `wifi_scan`'s results) round out a full on-site survey,
all via the same Sites → Scans model and results/export UI. See "Extending with new scan types"
below for how a scan type plugs in.

**Linux only, by design, with no plans to change.** `wifi_scan` shells out to `nmcli`
(NetworkManager) and `bluetooth_scan` uses `bleak` over BlueZ's D-Bus API — both Linux-specific.
`router_screenshot` itself is OS-agnostic (Playwright works cross-platform), but the project as a
whole targets Linux; there's no macOS/Windows scanner planned and no reason to expect one.

This README is a quick-start overview — see [`docs/`](docs/README.md) for a full option-by-option
reference on every scan type, the offline vendor-identification database, the REST API, and how
the `ScanRunner` plugin architecture works.

## Safety model

This drives a *real* router's admin interface, so the crawler is built to be structurally
incapable of triggering a destructive action (Reboot, Factory Reset, Apply, firmware upload,
etc.):

- After the initial login, the crawler's default source of navigation is `<a href>` targets found
  in each page's rendered HTML (see `crawler/pennypincher_crawler/link_filter.py`). It never
  clicks a button or submits any form other than the login form.
- Links are further restricted to the router's own origin (host/port) — it won't wander off to an
  external "support" link, for example.
- A max-pages safety cap (`options.max_pages`, default 200) bounds runaway crawls from link
  cycles or huge nav menus.
- **Nav-button exploration** (`options.click_nav`, default **on**). Some admin UIs (React/Vue
  SPAs especially) implement their settings navigation with onClick-driven buttons instead of
  real links, which the link-only crawl above structurally cannot see — on one real router,
  real links alone reached only 3 of 22 actual settings pages, the rest sitting behind sidebar
  accordion buttons. So this runs by default, but with two independent safety layers, not just
  one (`crawler/pennypincher_crawler/click_filter.py`):
  1. **Filter before clicking**: only considers buttons inside a nav/sidebar landmark, never a
     `type=submit` control, never anything inside a `<form>`, and never anything whose label
     matches a broad danger-keyword list (reboot, reset, delete, apply, save, firmware, etc).
  2. **Hard backstop while clicking**: every non-GET network request is blocked for the duration
     of each exploratory click. So even if a button's label doesn't give away that it's
     destructive, clicking it still can't reach the router as a mutating request — this was
     verified with a decoy "Sync Now" button that actually fires a POST on click; the POST is
     aborted and the button's true target never sees it.
  This still shares one limitation with the link-only crawl: a *GET*-based destructive endpoint
  (bad API design, but it exists on some devices) isn't caught by the non-GET block. Uncheck it
  in the Advanced section (or pass `click_nav: false`) to restrict a scan to real links only.

## Architecture

```
backend/    FastAPI app — REST API, site/scan orchestration, serves the frontend
crawler/    Scrapy + scrapy-playwright project — the router_screenshot scan type's implementation
scanners/   Standalone scripts (no Scrapy) — wifi_scan, bluetooth_scan, network_devices_scan, and
            the bundled local vendor-lookup databases (scanners/data/)
frontend/   Static HTML/JS/CSS single-page app
data/       Gitignored — data/sites/<site_id>/scans/<scan_id>/{status.json, manifest.json, artifacts/}
tests/      Unit tests, no live router, WiFi/Bluetooth adapter, or GUI required
```

**Sites → Scans.** A *Site* is a physical address (created by typing it into the GUI, or reused if
it already exists — see `backend/sites.py`). A *Scan* is one run of one scan type at a site (e.g.
one router crawl); a site can have many scans over time. Each scan gets its own directory holding
its status, its results manifest, and its captured files.

**Why the crawler runs as a subprocess.** Scrapy runs on the Twisted reactor, which can only start
once per OS process — it can't be invoked in-process, repeatedly, from the long-lived FastAPI
server. Each scan instead launches `scrapy crawl router_spider ...` as its own subprocess
(`backend/runners/router_screenshot.py`), writing output into that scan's directory. The FastAPI
backend polls the subprocess for completion.

**Credentials.** Entered live in the GUI per scan, passed into the crawler subprocess via
environment variables (not CLI args, so they don't show up in `ps`), and never written to
`status.json`, `manifest.json`, or any log file.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Running

```
uvicorn backend.app:app --reload
```

Then open http://127.0.0.1:8000 — enter an address to create/open a site, then "New scan" to
start a router capture (router URL, auth type, username/password, and an optional "Advanced"
section for CSS-selector overrides if the login page's fields can't be auto-detected).

A few things worth knowing about real routers:

- **Password-only login.** Leave the username field blank — `FormAuthStrategy` only fills it in
  if both a username field is found *and* you gave it a username, so a router with no username
  field (or one you're intentionally skipping) works fine.
- **Self-signed HTTPS.** Router admin UIs commonly serve HTTPS with a self-signed cert; the
  crawler launches Chromium with `--ignore-certificate-errors` (see
  `crawler/pennypincher_crawler/settings.py`) so this isn't a problem — just use the `https://`
  URL directly rather than an `http://` interstitial/warning page some routers show first.
- **Anti-bot honeypot fields.** Some login pages include a decoy `<input type="password">` hidden
  off-screen to trip up naive automation. The default password-field detection skips any password
  input with `tabindex="-1"` (a near-universal honeypot signal) in favor of one still in the tab
  order. If a login page still gets the wrong field (e.g. more than one *real* password input),
  give an explicit `password_selector` in the Advanced section.

### WiFi scanning

Pick "WiFi Scan" as the scan type instead — no URL/credentials needed, just a duration (seconds,
default 15) and an optional interface name. It repeatedly runs `nmcli device wifi list` for that
duration, de-duplicating by BSSID and keeping each network's most recent reading (useful if
walking around a site while it runs), and shows results as a table (SSID, BSSID, signal, channel,
security) sorted strongest-first. Export includes a `networks.csv` alongside `manifest.json` for
opening in a spreadsheet.

The results table is grouped by SSID for display — dual-band routers and mesh systems commonly
broadcast one SSID across several access points (different BSSID/channel each), which otherwise
reads as the same network showing up multiple times. The table shows the strongest AP's
BSSID/signal per group (with a "(+N more)" note when there's more than one); the underlying
`manifest.json`/`networks.csv` keep every access point as its own row, full detail intact — an
unexpected extra AP for a known SSID can itself be worth noticing (a rogue/evil-twin AP), not
just clutter to collapse away permanently.

Requires `nmcli` (part of NetworkManager — already present on most desktop Linux distros). This is
inherently a passive/read-only operation — listening for beacon frames can't mutate anything on
any network — so none of the router crawler's click-safety machinery is relevant here. If `nmcli`
reports no WiFi adapter (or isn't installed at all), the scan fails with that message rather than
silently returning zero networks.

### Bluetooth scanning

Pick "Bluetooth Scan" as the scan type — a duration (seconds, default 15) and an optional adapter
name (e.g. `hci0`). It scans continuously for that duration via `bleak` (BlueZ over D-Bus) and
shows results as a table (address, name, vendor, RSSI, manufacturer ID, service UUIDs) sorted
strongest-first. Export includes a `devices.csv` alongside `manifest.json`.

Requires `bluetoothd` (BlueZ) running with a working adapter — `systemctl status bluetooth` to
check. Same passive/read-only reasoning as WiFi scanning applies: nothing here can mutate a
discovered device, it's listening for advertisements only. If no adapter/daemon is reachable, the
scan fails with bleak's D-Bus error rather than hanging or silently returning zero devices.

### Scanning devices on a specific network

Not a directly-selectable scan type in the New Scan form — instead, open a completed `wifi_scan`'s
results and click "Scan devices" on a specific network's row. That starts a
`network_devices_scan` targeting that SSID and shows a table of what it finds (IP, MAC, vendor,
hostname).

You have to actually be joined to that WiFi network first (this scans the local subnet you're
currently on — it can't reach out to some other network you merely detected). The scan checks
this itself before doing anything: it reads which network you're currently connected to via
`nmcli` and refuses with a clear error if it doesn't match the SSID you clicked.

Discovery technique: ping every candidate address on your subnet once (concurrently, capped at a
2048-host safety limit) to populate the kernel's ARP/neighbor cache, then read it back via `ip
neighbor show`. This finds a host even if it doesn't answer ICMP itself — resolving an address's
MAC via ARP is a prerequisite of the kernel even attempting local-segment delivery, so just trying
to reach it triggers that regardless of whether the ping itself gets a reply. No root or raw
sockets needed, unlike `arp-scan`/`nmap`'s ARP-scan mode. Hostnames are filled in via a best-effort
reverse DNS lookup per device (works when a router's DHCP integrates with local DNS, which many
consumer routers do; otherwise left blank). Export includes a `devices.csv`.

### Vendor identification (offline)

`bluetooth_scan` and `network_devices_scan` results both include a **Vendor** column — resolved
entirely from two local databases bundled in `scanners/data/` (`oui_prefixes.json`,
~53,800 IEEE-registered MAC prefixes; `bluetooth_company_ids.json`, ~4,000 Bluetooth SIG company
IDs). **No network access at scan time** — `scanners/vendor_lookup.py` only ever reads these
already-built JSON files. For a MAC address, this matches its OUI prefix (trying IEEE's 36-bit,
28-bit, then 24-bit registries in that order, longest match wins) against the vendor that
registered it; a locally-administered/randomized address (the U/L bit set on the first octet —
common for BLE privacy addresses) is correctly reported as unresolvable rather than guessed, since
by definition no vendor registered it. For Bluetooth, this looks up the advertisement's
manufacturer company ID directly.

This resolves **manufacturer**, not exact model — "TP-Link Systems Inc." or "Apple, Inc.", not
"Archer AX55" or "iPhone 14". Getting to a specific model reliably generally needs either a cloud
fingerprint database or protocol-level fingerprinting (DHCP options, mDNS records, BLE GATT
services) — a meaningfully harder problem than a static lookup table, and not implemented here.

Both files were built from official public sources (IEEE's own MA-L/MA-M/MA-S OUI registries;
Bluetooth SIG's company identifiers, via Nordic Semiconductor's BSD-3-Clause-licensed
`bluetooth-numbers-database` mirror) and are periodically-stale by nature — new OUI/company ID
assignments happen continuously. To refresh them (this is the *only* thing in this repo that
calls the network, and it's a manual step you run yourself, never automatic):

```
python3 scanners/build_vendor_db.py
```

## Site reports

A site's page has "Download HTML report" / "Download Markdown report" once at least one scan
there has completed — a standalone summary (router screenshots from the latest scan, plus the
full WiFi/Bluetooth/network-device master lists) for sharing or filing outside the app. The HTML
version embeds screenshots as base64, so it's one self-contained file. See
[docs/reports.md](docs/reports.md) for the full breakdown.

## Testing

No live router or running server needed for the unit tests:

```
python3 -m unittest discover tests -v
```

- `test_link_filtering.py` — the crawler's default navigation safety boundary (same-origin,
  `<a href>`-only) against HTML fixtures, including one with a "Reboot" button/form to confirm
  it's never followed.
- `test_auth_strategies.py` — `FormAuthStrategy`'s username/password-field auto-detection
  (including skipping an anti-bot honeypot password field) against saved login-page fixtures.
  Needs `playwright install chromium`; skips itself otherwise.
- `test_click_filter.py` — the `click_nav` feature's danger-keyword label filter (the first of
  its two safety layers; the second — blocking non-GET requests during exploration — needs a
  real browser+server to exercise, see below).
- `test_site_ids.py` — address → site_id slugging and site-reuse logic, against a temp directory.
- `test_nmcli_parse.py` — the WiFi scan's `nmcli` terse-output parser, including the
  escaped-colon-inside-a-BSSID case that would break a naive `split(":")`. No real WiFi adapter
  needed — `scanners/wifi_scan.py` can also be run directly
  (`python3 scanners/wifi_scan.py --scan-dir /tmp/x --duration 5`) to sanity-check the full
  scan/dedup/manifest-writing loop even on a machine with zero visible networks.
- `test_bluetooth_parse.py` — the Bluetooth scan's device-record normalizer (manufacturer ID hex
  formatting, missing-data defaults). No real adapter needed — `scanners/bluetooth_scan.py` can
  likewise be run directly to sanity-check the full loop.
- `test_lan_devices_parse.py` — the network-devices scan's `nmcli`/`ip neighbor` parsers and
  subnet math (host enumeration excluding network/broadcast/self). The underlying ping-sweep +
  `ip neighbor` discovery technique itself was verified against a real live subnet during
  development (real hosts, real MACs, zero root needed) — that part isn't something a unit test
  can exercise without real network access, so it isn't re-asserted here.
- `test_vendor_lookup.py` — the offline MAC/Bluetooth vendor lookups, against the real bundled
  data files (so this also catches a broken/missing data file, not just logic bugs) using
  well-known stable values (e.g. Apple's `00:03:93` OUI and Bluetooth company ID 76), plus the
  locally-administered-address exclusion and longest-prefix-match preference.
- `test_csv_fieldnames.py` — a regression test asserting each scanner's `CSV_FIELDNAMES` exactly
  matches its `normalize_*()` output keys (a real bug: `vendor` was added to two scanners'
  normalized records without their CSV writer's field list being updated to match, which crashed
  the scan — after `manifest.json` had already been written correctly — the moment it got to a row
  with that field).
- `test_aggregate.py` — the site-wide "master list" merge/dedup logic (`backend/scans.py::
  get_aggregate()`), against a temp data directory with fabricated multi-scan data.
- `test_report.py` — the HTML/Markdown site report generators, including that a real screenshot's
  exact base64 encoding appears in the HTML output and that untrusted-looking content (site notes,
  titles) is properly escaped rather than injected as raw markup.

For an end-to-end check, run the backend and a small local page (or router) that has a login form
and a couple of linked pages, submit a scan through the GUI, and confirm the gallery + export
work.

## Extending with new scan types

A scan type is a `ScanRunner` (`backend/runners/base.py`) — one method, `launch(scan_dir,
params)`, that starts a subprocess and returns a handle with `.poll()`. It's free to do anything
as long as it writes `manifest.json` and any output files into `scan_dir/artifacts/`. Register it
in `backend/runners/__init__.py`'s `RUNNERS` map and add an entry to `SCAN_TYPES` in
`frontend/app.js` — no other backend or frontend code needs to change.

`wifi_scan`, `bluetooth_scan`, and `network_devices_scan` (`backend/runners/*.py` +
`scanners/*.py`) are examples of the same pattern beyond `router_screenshot` — all scan from the
machine physically present at the site rather than a remote URL, and need no Scrapy/Playwright at
all, just a subprocess shelling out to `nmcli`/bleak/`ip`. A future scan type follows the same
shape: a runner + a script, registered in one place, no changes needed to `backend/sites.py` or
`backend/scans.py`.

A scan type also doesn't have to be directly selectable in the New Scan form's dropdown —
`network_devices_scan` isn't; it's only reachable via a "Scan devices" button on a `wifi_scan`'s
results (`frontend/app.js`'s `scanDevicesButton`), since it only makes sense once you know which
SSID to target. `SCAN_TYPES` controls what shows up in that dropdown; a runner registered in
`RUNNERS` without a `SCAN_TYPES` entry is simply launched some other way in the UI.

## Releasing a new version

The `VERSION` file at the repo root is the single source of truth — `backend/app.py` reads it at
startup and serves it at `GET /version`; the frontend header fetches that on load and shows it
next to the title. To cut a release:

```
# 1. bump the VERSION file (semver: MAJOR.MINOR.PATCH — PATCH for a fix, MINOR for a new
#    feature, MAJOR only for a breaking change), then commit it
git commit -am "Bump version to X.Y.Z"

# 2. tag and push
git tag vX.Y.Z
git push origin main vX.Y.Z

# 3. let GitHub write the release notes from the commits since the last tag
gh release create vX.Y.Z --generate-notes
```
