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
    is_starred: bool = False


class SqliteJobsResponse(BaseModel):
    """SQLite 職缺分頁查詢回應。"""
    status: str
    data: List[SqliteJobItem]
    total: int
    page: int
    total_pages: int
    latest_count: int
    starred_count: Optional[int] = 0
    message: Optional[str] = None


class ChromaJobItem(BaseModel):
    """ChromaDB 單筆職缺格式。"""
    id: str
    metadata: Dict[str, Any]
    document: str
    is_latest: bool = False
    is_starred: bool = False


class ChromaJobsResponse(BaseModel):
    """ChromaDB 職缺分頁查詢回應。"""
    status: str
    data: List[ChromaJobItem]
    total_in_db: int
    page: int
    total_pages: int
    latest_count: int
    starred_count: Optional[int] = 0
    message: Optional[str] = None


class ToggleStarResponse(BaseModel):
    """切換職缺關注狀態回應。"""
    status: str
    job_id: str
    is_starred: bool
    starred_count: int
    message: Optional[str] = None


class StarredJobsResponse(BaseModel):
    """已關注職缺 ID 清單回應。"""
    status: str
    data: List[str]
    count: int

