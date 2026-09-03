from typing import Optional

from pydantic import BaseModel


class SiteCreateRequest(BaseModel):
    address: str
    notes: Optional[str] = None


class SiteResponse(BaseModel):
    site_id: str
    address: str
    created_at: str
    notes: Optional[str] = None
    scan_count: int = 0
    last_scan_at: Optional[str] = None


class ScanCreateRequest(BaseModel):
    scan_type: str
    params: dict = {}


class ScanResponse(BaseModel):
    scan_id: str
    scan_type: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    error: Optional[str] = None
    page_count: Optional[int] = None
