"""Scan = one run of one scan type at a Site. Lives under
data/sites/<site_id>/scans/<scan_id>/{status.json, manifest.json, artifacts/}.

Orchestration here is generic across scan types: it creates the scan directory, hands off to the
scan_type's ScanRunner (see runners/), and polls the returned subprocess handle for completion.
"""

import json
import zipfile
from datetime import datetime, timezone

from .runners import RUNNERS
from .sites import DATA_DIR as SITES_DIR

_RUNNING = {}  # scan_id -> subprocess handle, for polling completion


def _scan_dir(site_id, scan_id):
    return SITES_DIR / site_id / "scans" / scan_id


def _new_scan_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _write_status(scan_dir, **fields):
    status_file = scan_dir / "status.json"
    current = json.loads(status_file.read_text()) if status_file.exists() else {}
    current.update(fields)
    status_file.write_text(json.dumps(current, indent=2))
    return current


def create_scan(site_id, scan_type, params):
    if scan_type not in RUNNERS:
        raise ValueError(f"scan_type {scan_type!r} is not implemented yet (known: {sorted(RUNNERS)})")

    scan_id = _new_scan_id()
    scan_dir = _scan_dir(site_id, scan_id)
    (scan_dir / "artifacts").mkdir(parents=True, exist_ok=True)

    _write_status(
        scan_dir,
        scan_type=scan_type,
        status="running",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=None,
        error=None,
    )

    handle = RUNNERS[scan_type].launch(scan_dir, params)
    _RUNNING[scan_id] = handle
    return scan_id


def get_scan_status(site_id, scan_id):
    scan_dir = _scan_dir(site_id, scan_id)
    status_file = scan_dir / "status.json"
    if not status_file.exists():
        return None

    status = json.loads(status_file.read_text())

    handle = _RUNNING.get(scan_id)
    if status.get("status") == "running" and handle is not None:
        returncode = handle.poll()
        if returncode is not None:
            del _RUNNING[scan_id]
            status = _write_status(
                scan_dir,
                status="done" if returncode == 0 else "error",
                finished_at=datetime.now(timezone.utc).isoformat(),
                error=None if returncode == 0 else f"scan process exited with code {returncode}",
            )

    manifest_file = scan_dir / "manifest.json"
    if manifest_file.exists():
        status["page_count"] = len(json.loads(manifest_file.read_text()))

    status["scan_id"] = scan_id
    return status


def list_scans(site_id):
    scans_dir = SITES_DIR / site_id / "scans"
    if not scans_dir.exists():
        return []
    return [get_scan_status(site_id, p.name) for p in sorted(scans_dir.iterdir())]


def latest_scan(site_id, scan_type):
    """The most recently *completed* scan of a type at a site, or None. Directory names are
    scan_ids (UTC timestamps), so iterating newest-first is a plain reverse sort."""
    scans_dir = SITES_DIR / site_id / "scans"
    if not scans_dir.exists():
        return None
    for scan_path in sorted(scans_dir.iterdir(), reverse=True):
        status = get_scan_status(site_id, scan_path.name)
        if status and status.get("scan_type") == scan_type and status.get("status") == "done":
            return status
    return None


# Field that identifies "the same network/device" across separate scans of a given type, for
# AGGREGATE_KEYS below.
AGGREGATE_KEYS = {
    "wifi_scan": "bssid",
    "bluetooth_scan": "address",
    "network_devices_scan": "mac",
}

# Mirrors each scan type's own within-scan sort (strongest-signal-first, or numeric IP order) —
# merged rows carry whichever scan's reading is freshest, so sorting by that field the same way
# still reads naturally once merged.
_AGGREGATE_SORT_KEYS = {
    "wifi_scan": lambda row: (row.get("signal") is None, -(row.get("signal") or 0)),
    "bluetooth_scan": lambda row: (row.get("rssi") is None, -(row.get("rssi") or -999)),
    "network_devices_scan": lambda row: tuple(int(p) for p in row.get("ip", "0.0.0.0").split(".")),
}


def get_aggregate(site_id, scan_type):
    """Merges every completed scan of `scan_type` at a site into one deduplicated list — e.g.
    "every WiFi network ever seen here across all WiFi scans", not just one scan's results.
    Dedup key is scan-type-specific (AGGREGATE_KEYS); each row also gets first_seen_at/
    last_seen_at (that key's earliest/latest contributing scan's started_at) and times_seen (how
    many separate scans contained it) — otherwise, a row's fields are whichever scan saw it most
    recently, since that's the freshest read on it.
    """
    key_field = AGGREGATE_KEYS.get(scan_type)
    if key_field is None:
        raise ValueError(f"aggregation isn't supported for scan_type {scan_type!r}")

    scans_dir = SITES_DIR / site_id / "scans"
    if not scans_dir.exists():
        return []

    merged = {}
    # Directory names are scan_ids (UTC timestamps), so a plain sort is chronological order —
    # iterating oldest-to-newest means each key's fields naturally end up as its latest reading.
    for scan_path in sorted(scans_dir.iterdir()):
        status_file = scan_path / "status.json"
        manifest_file = scan_path / "manifest.json"
        if not status_file.exists() or not manifest_file.exists():
            continue

        status = json.loads(status_file.read_text())
        if status.get("scan_type") != scan_type or status.get("status") != "done":
            continue
        scan_time = status.get("started_at")

        for row in json.loads(manifest_file.read_text()):
            key = row.get(key_field)
            if not key:
                continue
            if key not in merged:
                merged[key] = {**row, "first_seen_at": scan_time, "last_seen_at": scan_time, "times_seen": 1}
            else:
                entry = merged[key]
                entry.update(row)
                entry["last_seen_at"] = scan_time
                entry["times_seen"] += 1

    rows = list(merged.values())
    sort_key = _AGGREGATE_SORT_KEYS.get(scan_type)
    if sort_key:
        rows.sort(key=sort_key)
    return rows


def get_manifest(site_id, scan_id):
    manifest_file = _scan_dir(site_id, scan_id) / "manifest.json"
    if not manifest_file.exists():
        return []
    return json.loads(manifest_file.read_text())


def artifact_path(site_id, scan_id, filename):
    artifacts_root = (_scan_dir(site_id, scan_id) / "artifacts").resolve()
    path = (artifacts_root / filename).resolve()
    if path != artifacts_root and artifacts_root not in path.parents:
        raise ValueError("invalid artifact path")
    return path


def export_scan_zip(site_id, scan_id):
    scan_dir = _scan_dir(site_id, scan_id)
    if not scan_dir.exists():
        return None

    zip_path = scan_dir / "export.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest_file = scan_dir / "manifest.json"
        if manifest_file.exists():
            zf.write(manifest_file, arcname="manifest.json")

        artifacts_dir = scan_dir / "artifacts"
        if artifacts_dir.exists():
            for file in artifacts_dir.iterdir():
                if file.is_file():
                    zf.write(file, arcname=f"artifacts/{file.name}")
    return zip_path
