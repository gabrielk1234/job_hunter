from fastapi import APIRouter
from schemas.job import ChromaJobsResponse, SqliteJobsResponse
from services.job_service import JobService
from services.scraper_service import scraper_manager

router = APIRouter(tags=["Jobs"])


@router.get("/api/sqlite-jobs", response_model=SqliteJobsResponse)
def get_sqlite_jobs(
    page: int = 1,
    limit: int = 20,
    keyword: str = "",
    latest_only: bool = False,
) -> SqliteJobsResponse:
    """從 SQLite 撈取原始職缺 JSON 資料與分頁資訊。"""
    result = JobService.get_sqlite_jobs(
        page=page,
        limit=limit,
        keyword=keyword,
        latest_only=latest_only,
        latest_ids=scraper_manager.latest_scraped_job_ids,
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
) -> ChromaJobsResponse:
    """從 ChromaDB 撈取向量化後的 Metadata 與 Documents 資料。"""
    result = JobService.get_chroma_jobs(
        page=page,
        limit=limit,
        min_salary=min_salary,
        min_hr_pr=min_hr_pr,
        keyword=keyword,
        latest_only=latest_only,
        latest_ids=scraper_manager.latest_scraped_job_ids,
    )
    return ChromaJobsResponse(**result)
