import math
from typing import Any, Dict, List, Optional
from repositories.job_repository import JobRepository


class JobService:
    """處理職缺資料檢索與篩選運算之商業邏輯。"""

    @staticmethod
    def get_sqlite_jobs(
        page: int = 1,
        limit: int = 20,
        keyword: str = "",
        latest_only: bool = False,
        starred_only: bool = False,
        latest_ids: Optional[List[str]] = None,
        starred_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """處理 SQLite 原始職缺資料查詢、最新標籤比對與分頁計算。"""
        current_latest_ids = latest_ids or []
        db_starred_ids = (
            starred_ids
            if starred_ids is not None
            else JobRepository.get_starred_job_ids()
        )

        if starred_only:
            if not db_starred_ids:
                return {
                    "status": "success",
                    "data": [],
                    "total": 0,
                    "page": 1,
                    "total_pages": 1,
                    "latest_count": len(current_latest_ids),
                    "starred_count": 0,
                }
            filter_ids = db_starred_ids
        elif latest_only:
            if not current_latest_ids:
                return {
                    "status": "success",
                    "data": [],
                    "total": 0,
                    "page": 1,
                    "total_pages": 1,
                    "latest_count": 0,
                    "starred_count": len(db_starred_ids),
                }
            filter_ids = current_latest_ids
        else:
            filter_ids = None

        total_count, jobs = JobRepository.get_sqlite_jobs(
            page=page,
            limit=limit,
            keyword=keyword,
            filter_ids=filter_ids,
            latest_ids=current_latest_ids,
            starred_ids=db_starred_ids,
        )

        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        return {
            "status": "success",
            "data": jobs,
            "total": total_count,
            "page": page,
            "total_pages": total_pages,
            "latest_count": len(current_latest_ids),
            "starred_count": len(db_starred_ids),
        }

    @staticmethod
    def get_chroma_jobs(
        page: int = 1,
        limit: int = 20,
        min_salary: int = 0,
        min_hr_pr: float = 0.0,
        keyword: str = "",
        latest_only: bool = False,
        starred_only: bool = False,
        latest_ids: Optional[List[str]] = None,
        starred_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """組合 ChromaDB 篩選條件，檢索向量資料庫並計算分頁。"""
        current_latest_ids = latest_ids or []
        db_starred_ids = (
            starred_ids
            if starred_ids is not None
            else JobRepository.get_starred_job_ids()
        )

        if starred_only and not db_starred_ids:
            return {
                "status": "success",
                "data": [],
                "total_in_db": 0,
                "page": 1,
                "total_pages": 1,
                "latest_count": len(current_latest_ids),
                "starred_count": 0,
            }

        if latest_only and not current_latest_ids:
            return {
                "status": "success",
                "data": [],
                "total_in_db": 0,
                "page": 1,
                "total_pages": 1,
                "latest_count": 0,
                "starred_count": len(db_starred_ids),
            }

        offset = (page - 1) * limit
        conditions: List[Dict[str, Any]] = []

        if starred_only:
            if len(db_starred_ids) == 1:
                conditions.append({"job_id": {"$eq": db_starred_ids[0]}})
            elif len(db_starred_ids) > 1:
                conditions.append({"job_id": {"$in": db_starred_ids}})
        elif latest_only:
            if len(current_latest_ids) == 1:
                conditions.append({"job_id": {"$eq": current_latest_ids[0]}})
            elif len(current_latest_ids) > 1:
                conditions.append({"job_id": {"$in": current_latest_ids}})

        if min_salary > 0:
            if min_salary <= 40000:
                conditions.append({"salaryMin": {"$gte": min_salary}})
            else:
                conditions.append(
                    {
                        "$or": [
                            {"salaryMin": {"$gte": min_salary}},
                            {"salaryMin": {"$eq": 0}},
                        ]
                    }
                )

        if min_hr_pr > 0:
            conditions.append({"hrBehaviorPR": {"$gte": float(min_hr_pr)}})

        if keyword:
            conditions.append(
                {
                    "$or": [
                        {"job_id": {"$contains": keyword}},
                        {"jobName": {"$contains": keyword}},
                        {"custName": {"$contains": keyword}},
                    ]
                }
            )

        where_clause: Optional[Dict[str, Any]] = None
        if len(conditions) == 1:
            where_clause = conditions[0]
        elif len(conditions) > 1:
            where_clause = {"$and": conditions}

        total_in_db, raw_jobs = JobRepository.get_chroma_jobs(
            offset=offset, limit=limit, where_clause=where_clause
        )

        jobs: List[Dict[str, Any]] = []
        for r in raw_jobs:
            meta = r.get("metadata", {})
            job_id_val = str(meta.get("job_id", "") or r["id"])
            jobs.append(
                {
                    "id": r["id"],
                    "metadata": meta,
                    "document": r["document"],
                    "is_latest": job_id_val in current_latest_ids,
                    "is_starred": job_id_val in db_starred_ids,
                }
            )

        total_pages = math.ceil(total_in_db / limit) if total_in_db > 0 else 1

        return {
            "status": "success",
            "data": jobs,
            "total_in_db": total_in_db,
            "page": page,
            "total_pages": total_pages,
            "latest_count": len(current_latest_ids),
            "starred_count": len(db_starred_ids),
        }

    @staticmethod
    def toggle_star_job(job_id: str) -> Dict[str, Any]:
        """切換關注狀態並回傳最新狀態。"""
        is_starred, total_starred = JobRepository.toggle_star_job(job_id)
        return {
            "status": "success",
            "job_id": job_id,
            "is_starred": is_starred,
            "starred_count": total_starred,
        }

    @staticmethod
    def get_starred_job_ids() -> List[str]:
        """取得所有關注中的 job_id。"""
        return JobRepository.get_starred_job_ids()
