# Architecture

```
backend/    FastAPI app — REST API, site/scan orchestration, serves the frontend
crawler/    Scrapy + scrapy-playwright project — the router_screenshot scan type's implementation
scanners/   Standalone scripts (no Scrapy) — wifi_scan, bluetooth_scan, network_devices_scan, and
            the bundled local vendor-lookup databases (scanners/data/)
frontend/   Static HTML/JS/CSS single-page app
data/       Gitignored — data/sites/<site_id>/scans/<scan_id>/{status.json, manifest.json, artifacts/}
tests/      Unit tests, no live router, WiFi/Bluetooth adapter, or GUI required
```

## Sites → Scans

- **Site** = a physical address. Created by typing it into the GUI (`POST /sites`), or reused if
  it already exists (`backend/sites.py::get_or_create_site`). `site_id_for()` derives a
  deterministic, readable ID from the address (`_slugify(address)` + an 8-char hash of the
  lowercased/trimmed address) — so re-posting a trivially-differently-formatted version of an
  address you've already used (different case, extra whitespace) reuses the same site rather than
  forking it. Metadata only: `{address, created_at, notes}`.
- **Scan** = one run of one scan type at a site. A site can have many scans over time, of
  different types. Each scan gets its own directory:

  ```
  data/sites/<site_id>/
  ├── site.json
  └── scans/
      └── <scan_id>/           # scan_id = UTC timestamp, e.g. 20260903T120000123456
          ├── status.json      # {scan_type, status, started_at, finished_at, error}
          ├── manifest.json    # scan-type-specific results list
          ├── crawler.log / scan.log   # the runner subprocess's stdout+stderr
          └── artifacts/       # screenshots, CSVs, per-page HTML — whatever that scan type produces
  ```

  `backend/scans.py::create_scan()` creates this directory structure and `status.json`, then
  dispatches to the scan type's `ScanRunner`. `get_scan_status()` polls the runner's subprocess
  handle and updates `status.json` once it exits (`done` on a zero exit code, `error` otherwise,
  with `status.json`'s `error` field set to a message built from the exit code — a scan type
  raising a clear error and exiting non-zero, rather than exiting 0 with bad data, is how a failure
  surfaces to the GUI).

## The `ScanRunner` plugin interface

`backend/runners/base.py`:

```python
class ScanRunner(ABC):
    @abstractmethod
    def launch(self, scan_dir, params):
        """Starts the scan as a subprocess for `scan_dir` (already created, with an artifacts/
        subdirectory) using `params` (the request body's params object). Returns a handle with a
        `.poll()` method (e.g. subprocess.Popen) that the backend polls for completion."""
```

That's the entire contract. A runner is free to do anything as long as it eventually writes
`manifest.json` (a JSON list — its exact shape is entirely up to the scan type) and any output
files into `scan_dir/artifacts/`, then exits zero on success / non-zero on failure.

Register a runner in `backend/runners/__init__.py`'s `RUNNERS` dict, keyed by the `scan_type`
string used in API requests:

```python
RUNNERS = {
    "router_screenshot": RouterScreenshotRunner(),
    "wifi_scan": WifiScanRunner(),
    "bluetooth_scan": BluetoothScanRunner(),
    "network_devices_scan": LanDevicesScanRunner(),
}
```

Nothing in `backend/sites.py` or `backend/scans.py` needs to change to add a new scan type —
they're already generic across whatever's in `RUNNERS`.

### Why every runner launches a subprocess

`router_screenshot` *must* — Scrapy runs on the Twisted reactor, which can only start once per OS
process, so it can't be invoked in-process, repeatedly, from the long-lived FastAPI server.

The other three scan types (`wifi_scan`, `bluetooth_scan`, `network_devices_scan`) don't share
that constraint — they're just a handful of subprocess calls to `nmcli`/`bleak`/`ip` — but launch
as subprocesses anyway, for consistency with `router_screenshot` and so a slow scan can't block
the FastAPI server's event loop.

Every runner invokes its script via `sys.executable` (e.g. `[sys.executable, "-m", "scrapy", ...]`
or `[sys.executable, str(SCANNER_SCRIPT), ...]`) rather than a bare command name resolved off
`PATH` — this makes the subprocess launch work regardless of how the FastAPI process itself was
started (a bare `"scrapy"` on `PATH` breaks if the venv wasn't activated in the shell that started
uvicorn, for example).

### Credentials

`router_screenshot`'s username/password are passed into the crawler subprocess via **environment
variables** (`PENNYPINCHER_USERNAME`/`PENNYPINCHER_PASSWORD`), not CLI args — so they never show
up in `ps`. They're never written to `status.json`, `manifest.json`, or any log file. No other
scan type takes credentials.

## A scan type doesn't have to be in the New Scan dropdown

`SCAN_TYPES` in `frontend/app.js` controls what shows up in the New Scan form's dropdown — it's a
separate thing from `RUNNERS`, the actual registry of what scan types exist. `network_devices_scan`
is registered in `RUNNERS` like any other scan type, fully functional via the API, but deliberately
absent from `SCAN_TYPES`: it only makes sense once you already know which SSID to target, so it's
launched contextually instead, from a "Scan devices" button on a WiFi Scan's results
(`scanDevicesButton()` in `frontend/app.js`). A future scan type can follow either pattern.

## Adding a new scan type — checklist

1. Write the actual scan logic as a standalone script under `scanners/` (or a Scrapy spider under
   `crawler/`, if it genuinely needs browser automation) that takes a `--scan-dir` and writes
   `manifest.json` + `artifacts/` there. Keep any output-parsing logic in a separate, pure-function
   module (see `scanners/nmcli_parse.py`, `scanners/lan_devices_parse.py`,
   `scanners/bluetooth_parse.py`) so it's unit-testable without the real hardware/daemon.
2. Write a `ScanRunner` in `backend/runners/<name>.py` that launches that script as a subprocess.
3. Register it in `backend/runners/__init__.py`'s `RUNNERS`.
4. Frontend: add result-table columns to `TABLE_COLUMNS` (and entries in `COUNT_LABELS`/
   `EMPTY_LABELS`) in `frontend/app.js`. Add an entry to `SCAN_TYPES` if it should be directly
   selectable in the New Scan form (with whatever param fields it needs); otherwise wire up
   whatever contextual trigger makes sense instead.
5. Tests for the pure-function parsing/normalization module. Where possible, verify the underlying
   mechanism against something real during development (a real subnet, a real device) even if it
   can't be asserted in an automated test without that hardware present.
6. Document it under `docs/scans/`, and link it from `docs/README.md`.

## Frontend

Static HTML/JS/CSS, no build step, no framework — `frontend/app.js` is a small hand-rolled
SPA-style app (hash-based routing, a handful of `render*` functions, a generic `el()` helper for
building DOM nodes, a generic `renderTable(rows, columns, context)` for tabular results). Served
directly by FastAPI's `StaticFiles` mount in `backend/app.py`.

## See also

- [API reference](api-reference.md) for the actual HTTP endpoints.
- [Router Screenshot](scans/router-screenshot.md), [WiFi Scan](scans/wifi-scan.md),
  [Bluetooth Scan](scans/bluetooth-scan.md), [Network Devices Scan](scans/network-devices-scan.md)
  for each scan type's own internals.
