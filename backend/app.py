from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import scans, sites
from .models import ScanCreateRequest, ScanResponse, SiteCreateRequest, SiteResponse

app = FastAPI(title="PennyPincher")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.post("/sites", response_model=SiteResponse)
def create_site(body: SiteCreateRequest):
    site_id = sites.get_or_create_site(body.address, body.notes)
    return sites.get_site(site_id)


@app.get("/sites", response_model=List[SiteResponse])
def get_sites():
    return sites.list_sites()


@app.get("/sites/{site_id}", response_model=SiteResponse)
def get_site(site_id: str):
    site = sites.get_site(site_id)
    if site is None:
        raise HTTPException(404, "site not found")
    return site


@app.post("/sites/{site_id}/scans", response_model=ScanResponse)
def create_scan(site_id: str, body: ScanCreateRequest):
    if sites.get_site(site_id) is None:
        raise HTTPException(404, "site not found")
    try:
        scan_id = scans.create_scan(site_id, body.scan_type, body.params)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return scans.get_scan_status(site_id, scan_id)


@app.get("/sites/{site_id}/scans", response_model=List[ScanResponse])
def list_scans(site_id: str):
    return scans.list_scans(site_id)


@app.get("/sites/{site_id}/scans/{scan_id}", response_model=ScanResponse)
def get_scan(site_id: str, scan_id: str):
    status = scans.get_scan_status(site_id, scan_id)
    if status is None:
        raise HTTPException(404, "scan not found")
    return status


@app.get("/sites/{site_id}/scans/{scan_id}/results")
def get_scan_results(site_id: str, scan_id: str):
    return scans.get_manifest(site_id, scan_id)


@app.get("/sites/{site_id}/scans/{scan_id}/artifacts/{filename}")
def get_artifact(site_id: str, scan_id: str, filename: str):
    try:
        path = scans.artifact_path(site_id, scan_id, filename)
    except ValueError:
        raise HTTPException(400, "invalid artifact path")
    if not path.exists():
        raise HTTPException(404, "artifact not found")
    return FileResponse(path)


@app.get("/sites/{site_id}/scans/{scan_id}/export")
def export_scan(site_id: str, scan_id: str):
    zip_path = scans.export_scan_zip(site_id, scan_id)
    if zip_path is None:
        raise HTTPException(404, "scan not found")
    return FileResponse(zip_path, filename=f"{site_id}_{scan_id}.zip", media_type="application/zip")


# Static frontend last, so it doesn't shadow the API routes above.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
