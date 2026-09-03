# PennyPincher

Logs into a router's web admin UI, crawls every settings page it can reach via on-page links, and
screenshots each one — organized by the physical **site** (address) it was captured at, since the
same tool gets run at multiple locations. A web frontend lets you enter an address, kick off a
capture with live credentials (never stored to disk), watch it run, browse the resulting
screenshots (each captioned with the URL it came from), and export everything as a zip.

Router "scans" are one of several **scan types** at a site. A `wifi_scan` type (nearby WiFi
networks, via `nmcli` on Linux) is also implemented; a future `bluetooth_scan` can be added the
same way — the architecture doesn't need to change to add scan types beyond the URL-crawling
model. See "Extending with new scan types" below.

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
- **Optional nav-button exploration** (`options.click_nav`, default off). Some admin UIs
  (React/Vue SPAs especially) implement their settings navigation with onClick-driven buttons
  instead of real links, which the link-only crawl above structurally cannot see. When enabled,
  the crawler also explores nav/sidebar buttons — but with two independent safety layers, not
  just one (`crawler/pennypincher_crawler/click_filter.py`):
  1. **Filter before clicking**: only considers buttons inside a nav/sidebar landmark, never a
     `type=submit` control, never anything inside a `<form>`, and never anything whose label
     matches a broad danger-keyword list (reboot, reset, delete, apply, save, firmware, etc).
  2. **Hard backstop while clicking**: every non-GET network request is blocked for the duration
     of each exploratory click. So even if a button's label doesn't give away that it's
     destructive, clicking it still can't reach the router as a mutating request — this was
     verified with a decoy "Sync Now" button that actually fires a POST on click; the POST is
     aborted and the button's true target never sees it.
  This still shares one limitation with the link-only crawl: a *GET*-based destructive endpoint
  (bad API design, but it exists on some devices) isn't caught by the non-GET block. Off by
  default for that reason — turn it on deliberately per scan in the Advanced section.

## Architecture

```
backend/    FastAPI app — REST API, site/scan orchestration, serves the frontend
crawler/    Scrapy + scrapy-playwright project — the router_screenshot scan type's implementation
scanners/   Standalone scripts (no Scrapy) — the wifi_scan scan type's implementation
frontend/   Static HTML/JS/CSS single-page app
data/       Gitignored — data/sites/<site_id>/scans/<scan_id>/{status.json, manifest.json, artifacts/}
tests/      Unit tests, no live router, WiFi adapter, or GUI required
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

Linux only for now (`nmcli`, part of NetworkManager — already present on most desktop Linux
distros). This is inherently a passive/read-only operation — listening for beacon frames can't
mutate anything on any network — so none of the router crawler's click-safety machinery is
relevant here. If `nmcli` reports no WiFi adapter (or isn't installed at all), the scan fails with
that message rather than silently returning zero networks.

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

For an end-to-end check, run the backend and a small local page (or router) that has a login form
and a couple of linked pages, submit a scan through the GUI, and confirm the gallery + export
work.

## Extending with new scan types

A scan type is a `ScanRunner` (`backend/runners/base.py`) — one method, `launch(scan_dir,
params)`, that starts a subprocess and returns a handle with `.poll()`. It's free to do anything
as long as it writes `manifest.json` and any output files into `scan_dir/artifacts/`. Register it
in `backend/runners/__init__.py`'s `RUNNERS` map and add an entry to `SCAN_TYPES` in
`frontend/app.js` — no other backend or frontend code needs to change.

`wifi_scan` (`backend/runners/wifi_scan.py` + `scanners/wifi_scan.py`) is a second, simpler
example of the same pattern — unlike `router_screenshot`, it scans from the machine physically
present at the site rather than a remote URL, and needs no Scrapy/Playwright at all, just a
subprocess repeatedly shelling out to `nmcli`.

Planned future scan types, not yet implemented:

- **`bluetooth_scan`** — nearby Bluetooth/BLE device discovery (e.g. via `bluetoothctl`/`bleak`).
  Needs its own design pass for what library to use, what OS permissions it needs, and what its
  `manifest.json` shape should record.
- **WiFi/Bluetooth scanning on macOS/Windows** — `wifi_scan` is Linux-only (`nmcli`) for now;
  Windows (`netsh wlan show networks`) and macOS (increasingly restricted by Apple without extra
  app entitlements) would each be their own `ScanRunner`, selected by `platform.system()` or a
  separate registered scan type.
