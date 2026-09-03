from typing import Optional
from pydantic import BaseModel


class ScraperStatusData(BaseModel):
    """爬蟲當前狀態資訊。"""
    is_running: bool
    progress: int
    logs_count: int
    latest_count: int


class ScraperStatusResponse(BaseModel):
    """爬蟲狀態回應。"""
    status: str
    data: ScraperStatusData
    message: Optional[str] = None
