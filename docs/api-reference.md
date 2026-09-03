# API reference

The REST API `frontend/app.js` talks to — also usable directly (see the `curl` examples below;
this is exactly how the scan-type docs' examples were exercised during development). Base URL:
wherever the backend is running, e.g. `http://127.0.0.1:8000`.

All request/response bodies are JSON. Models are defined in `backend/models.py`.

## Sites

### `POST /sites`

Creates a site, or returns the existing one for the same address (see
[Architecture](architecture.md#sites--scans) for how address → site_id works).

Request:
```json
{ "address": "123 Main St, Springfield", "notes": "optional" }
```

Response (`SiteResponse`):
```json
{
  "site_id": "123-main-st-springfield-f6728e0a",
  "address": "123 Main St, Springfield",
  "created_at": "2026-09-03T12:00:00+00:00",
  "notes": "optional",
  "scan_count": 0,
  "last_scan_at": null
}
```

### `GET /sites`

Returns `SiteResponse[]` — every known site.

### `GET /sites/{site_id}`

Returns one `SiteResponse`, or `404` if unknown.

## Scans

### `POST /sites/{site_id}/scans`

Starts a scan at a site. `404` if the site doesn't exist.

Request (`ScanCreateRequest`):
```json
{ "scan_type": "wifi_scan", "params": { "duration": 20 } }
```

`scan_type` must be a key in `backend/runners/__init__.py`'s `RUNNERS` — currently
`router_screenshot`, `wifi_scan`, `bluetooth_scan`, or `network_devices_scan`. An unregistered
`scan_type`, or a `params` object missing a scan type's required fields, returns `400` with a
message explaining what's wrong (both are the same `ValueError` → `HTTPException(400)` path in
`backend/app.py`). See each scan type's doc under [`scans/`](.) for its exact `params` shape.

Response (`ScanResponse`) — the scan has already been launched (as a background subprocess) by
the time this returns; `status` will normally be `"running"`:
```json
{
  "scan_id": "20260903T120000123456",
  "scan_type": "wifi_scan",
  "status": "running",
  "started_at": "2026-09-03T12:00:00+00:00",
  "finished_at": null,
  "error": null,
  "page_count": null
}
```

### `GET /sites/{site_id}/scans`

Returns `ScanResponse[]` for a site, in scan_id (creation) order.

### `GET /sites/{site_id}/scans/{scan_id}`

Returns one `ScanResponse` — poll this while `status` is `"running"`/`"pending"`. `status`
becomes `"done"` (exit code 0) or `"error"` (non-zero exit; `error` holds a message) once the
runner's subprocess finishes. `page_count` is the current length of `manifest.json` — despite the
name, this is a page count only for `router_screenshot`; for the other scan types it's really
"how many rows found so far" (networks/devices). `404` if the scan doesn't exist.

### `GET /sites/{site_id}/scans/{scan_id}/results`

Returns the scan's `manifest.json` verbatim — a JSON array whose element shape is entirely
scan-type-specific (see each scan type's doc for its exact fields). Empty array if the scan hasn't
produced any results (yet, or ever).

### `GET /sites/{site_id}/scans/{scan_id}/artifacts/{filename}`

Serves one file from the scan's `artifacts/` directory (a screenshot, a CSV, a saved HTML page —
whatever that scan type wrote there) as a raw file response. `400` if `filename` would resolve
outside `artifacts/` (path traversal), `404` if it doesn't exist.

### `GET /sites/{site_id}/scans/{scan_id}/export`

Zips the scan's `manifest.json` + everything in `artifacts/` on the fly and returns it as a file
download (`{site_id}_{scan_id}.zip`). `404` if the scan doesn't exist.

## Example: run a WiFi scan end-to-end via curl

```bash
SITE=$(curl -s -X POST http://127.0.0.1:8000/sites -H 'Content-Type: application/json' \
  -d '{"address": "123 Main St"}')
SITE_ID=$(echo "$SITE" | python3 -c "import json,sys; print(json.load(sys.stdin)['site_id'])")

SCAN=$(curl -s -X POST "http://127.0.0.1:8000/sites/$SITE_ID/scans" -H 'Content-Type: application/json' \
  -d '{"scan_type": "wifi_scan", "params": {"duration": 15}}')
SCAN_ID=$(echo "$SCAN" | python3 -c "import json,sys; print(json.load(sys.stdin)['scan_id'])")

# poll until status is no longer "running"/"pending"
curl -s "http://127.0.0.1:8000/sites/$SITE_ID/scans/$SCAN_ID"

# once done:
curl -s "http://127.0.0.1:8000/sites/$SITE_ID/scans/$SCAN_ID/results"
curl -s "http://127.0.0.1:8000/sites/$SITE_ID/scans/$SCAN_ID/export" -o scan.zip
```

## Everything else is static files

Any path not matched by the routes above falls through to a `StaticFiles` mount serving
`frontend/`, so `GET /` serves `frontend/index.html`, `GET /app.js` serves the frontend script,
etc. (`backend/app.py` mounts this last, specifically so it can never shadow an API route.)
