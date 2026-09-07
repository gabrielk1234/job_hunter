from typing import Optional
from fastapi import APIRouter
from schemas.job import (
    ChromaJobsResponse,
    SqliteJobsResponse,
    StarredJobsResponse,
    ToggleStarResponse,
)
from services.job_service import JobService
from services.scraper_service import scraper_manager

router = APIRouter(tags=["Jobs"])


@router.get("/api/sqlite-jobs", response_model=SqliteJobsResponse)
def get_sqlite_jobs(
    page: int = 1,
    limit: int = 20,
    keyword: str = "",
    latest_only: bool = False,
    starred_only: bool = False,
    starred_ids: Optional[str] = None,
) -> SqliteJobsResponse:
    """從 SQLite 撈取原始職缺 JSON 資料與分頁資訊。"""
    parsed_starred_ids = (
        [i.strip() for i in starred_ids.split(",") if i.strip()]
        if starred_ids is not None
        else None
    )
    result = JobService.get_sqlite_jobs(
        page=page,
        limit=limit,
        keyword=keyword,
        latest_only=latest_only,
        starred_only=starred_only,
        latest_ids=scraper_manager.latest_scraped_job_ids,
        starred_ids=parsed_starred_ids,
    )
    return SqliteJobsResponse(**result)


@router.get("/api/chroma-jobs", response_model=ChromaJobsResponse)
def get_chroma_jobs(
    page: int = 1,
    limit: int = 20,
    min_salary: int = 0,
    min_hr_pr: float = 0.0,
    keyword: str = "",
    latest_only: bool = False,
    starred_only: bool = False,
    starred_ids: Optional[str] = None,
) -> ChromaJobsResponse:
    """從 ChromaDB 撈取向量化後的 Metadata 與 Documents 資料。"""
    parsed_starred_ids = (
        [i.strip() for i in starred_ids.split(",") if i.strip()]
        if starred_ids is not None
        else None
    )
    result = JobService.get_chroma_jobs(
        page=page,
        limit=limit,
        min_salary=min_salary,
        min_hr_pr=min_hr_pr,
        keyword=keyword,
        latest_only=latest_only,
        starred_only=starred_only,
        latest_ids=scraper_manager.latest_scraped_job_ids,
        starred_ids=parsed_starred_ids,
    )
    return ChromaJobsResponse(**result)


@router.post("/api/toggle-star/{job_id}", response_model=ToggleStarResponse)
def toggle_star_job(job_id: str) -> ToggleStarResponse:
    """在 SQLite 資料庫中切換職缺之主要關注狀態。"""
    result = JobService.toggle_star_job(job_id)
    return ToggleStarResponse(**result)


@router.get("/api/starred-jobs", response_model=StarredJobsResponse)
def get_starred_jobs() -> StarredJobsResponse:
    """取得 SQLite 資料庫中所有已關注職缺 ID 清單。"""
    starred_ids = JobService.get_starred_job_ids()
    return StarredJobsResponse(
        status="success", data=starred_ids, count=len(starred_ids)
    )

