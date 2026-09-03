"""Site = a physical address being worked. Sites live under data/sites/<site_id>/ and hold only
metadata (address.json) plus a scans/ directory (see scans.py). site_id is derived deterministically
from the address, so re-creating a site with the same address reuses the existing one instead of
forking it.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sites"


def _slugify(address):
    slug = re.sub(r"[^a-z0-9]+", "-", address.strip().lower()).strip("-")
    return slug[:50] or "site"


def site_id_for(address):
    digest = hashlib.sha1(address.strip().lower().encode()).hexdigest()[:8]
    return f"{_slugify(address)}-{digest}"


def get_or_create_site(address, notes=None):
    site_id = site_id_for(address)
    site_dir = DATA_DIR / site_id
    site_file = site_dir / "site.json"
    (site_dir / "scans").mkdir(parents=True, exist_ok=True)

    if not site_file.exists():
        site_file.write_text(
            json.dumps(
                {
                    "address": address,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "notes": notes,
                },
                indent=2,
            )
        )
    return site_id


def get_site(site_id):
    site_file = DATA_DIR / site_id / "site.json"
    if not site_file.exists():
        return None

    data = json.loads(site_file.read_text())
    scans_dir = DATA_DIR / site_id / "scans"
    scan_dirs = sorted(p.name for p in scans_dir.iterdir()) if scans_dir.exists() else []

    data["site_id"] = site_id
    data["scan_count"] = len(scan_dirs)
    data["last_scan_at"] = scan_dirs[-1] if scan_dirs else None
    return data


def list_sites():
    if not DATA_DIR.exists():
        return []
    return [get_site(p.name) for p in sorted(DATA_DIR.iterdir()) if p.is_dir()]
