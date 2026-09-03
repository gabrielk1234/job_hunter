from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SqliteJobItem(BaseModel):
    """SQLite 單筆職缺格式。"""
    job_id: str
    custName: str
    jobName: str
    raw_json: str
    job_link: Optional[str] = None
    is_latest: bool = False


class SqliteJobsResponse(BaseModel):
    """SQLite 職缺分頁查詢回應。"""
    status: str
    data: List[SqliteJobItem]
    total: int
    page: int
    total_pages: int
    latest_count: int
    message: Optional[str] = None


class ChromaJobItem(BaseModel):
    """ChromaDB 單筆職缺格式。"""
    id: str
    metadata: Dict[str, Any]
    document: str
    is_latest: bool = False


class ChromaJobsResponse(BaseModel):
    """ChromaDB 職缺分頁查詢回應。"""
    status: str
    data: List[ChromaJobItem]
    total_in_db: int
    page: int
    total_pages: int
    latest_count: int
    message: Optional[str] = None
