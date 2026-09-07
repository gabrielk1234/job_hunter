import math
from typing import Any, Dict, List, Optional, Tuple
from database.connection import get_db_connection, get_chroma_collection
from tools.myown_tools import flatten


class JobRepository:
    """處理職缺資料在 SQLite 與 ChromaDB 中的 CRUD 操作。"""

    @staticmethod
    def get_sqlite_jobs(
        page: int = 1,
        limit: int = 20,
        keyword: str = "",
        filter_ids: Optional[List[str]] = None,
        latest_ids: Optional[List[str]] = None,
        starred_ids: Optional[List[str]] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """從 SQLite 分頁查詢職缺資料。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            where_clauses: List[str] = []
            search_params: List[Any] = []

            if filter_ids is not None:
                if not filter_ids:
                    return 0, []
                placeholders = ",".join(["?"] * len(filter_ids))
                where_clauses.append(f"job_id IN ({placeholders})")
                search_params.extend(filter_ids)

            if keyword:
                where_clauses.append("(job_id LIKE ? OR cust_name LIKE ? OR job_name LIKE ?)")
                like_kw = f"%{keyword}%"
                search_params.extend([like_kw, like_kw, like_kw])

            where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            count_query = f"SELECT COUNT(*) FROM job_documents{where_sql}"
            cursor.execute(count_query, tuple(search_params))
            total_count = cursor.fetchone()[0]

            offset = (page - 1) * limit
            select_query = (
                f"SELECT job_id, job_document, job_name, cust_name, job_link "
                f"FROM job_documents{where_sql} LIMIT ? OFFSET ?"
            )
            final_params = tuple(search_params) + (limit, offset)
            cursor.execute(select_query, final_params)
            rows = cursor.fetchall()

            jobs: List[Dict[str, Any]] = []
            for row in rows:
                job_id, job_data_str, job_name, cust_name, job_link = row
                try:
                    jobs.append(
                        {
                            "job_id": job_id,
                            "custName": cust_name,
                            "jobName": job_name,
                            "raw_json": flatten(job_data_str),
                            "job_link": job_link,
                            "is_latest": latest_ids is not None and job_id in latest_ids,
                            "is_starred": starred_ids is not None and job_id in starred_ids,
                        }
                    )
                except Exception:
                    continue

            return total_count, jobs

    @staticmethod
    def get_job_by_id(job_id: str) -> Optional[Dict[str, Any]]:
        """依據 job_id 查詢單筆 SQLite 職缺資料。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT job_id, job_document, job_name, cust_name, job_link FROM job_documents WHERE job_id = ?",
                (job_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "job_id": row[0],
                    "job_document": row[1],
                    "job_name": row[2],
                    "cust_name": row[3],
                    "job_link": row[4],
                }
            return None

    @staticmethod
    def upsert_job(
        job_id: str,
        job_document: str,
        job_name: str,
        cust_name: str,
        job_link: str,
    ) -> None:
        """寫入或更新職缺至 SQLite job_documents 資料表。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO job_documents (job_id, job_document, job_name, cust_name, job_link)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, job_document, job_name, cust_name, job_link),
            )
            conn.commit()

    @staticmethod
    def get_chroma_jobs(
        offset: int,
        limit: int,
        where_clause: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """從 ChromaDB 取得符合條件的職缺 documents 與 metadata。"""
        collection = get_chroma_collection()
        query_args: Dict[str, Any] = {"limit": limit, "offset": offset}
        if where_clause:
            query_args["where"] = where_clause

        results = collection.get(**query_args)

        if where_clause:
            all_filtered = collection.get(where=where_clause)
            total_in_db = (
                len(all_filtered["ids"])
                if all_filtered and all_filtered.get("ids")
                else 0
            )
        else:
            total_in_db = collection.count()

        jobs: List[Dict[str, Any]] = []
        if results and results.get("ids"):
            for i in range(len(results["ids"])):
                meta = results["metadatas"][i] if results["metadatas"] else {}
                jobs.append(
                    {
                        "id": results["ids"][i],
                        "metadata": meta,
                        "document": (
                            results["documents"][i] if results["documents"] else ""
                        ),
                    }
                )

        return total_in_db, jobs

    @staticmethod
    def get_chroma_metadata_by_id(job_id: str) -> Optional[Dict[str, Any]]:
        """從 ChromaDB 取得單筆職缺之 metadata。"""
        collection = get_chroma_collection()
        results = collection.get(where={"job_id": job_id}, limit=1)
        if results and results.get("metadatas") and len(results["metadatas"]) > 0:
            return results["metadatas"][0]
        return None

    @staticmethod
    def add_chroma_chunks(
        documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]
    ) -> None:
        """寫入或更新 Chunks 至 ChromaDB 集合。"""
        collection = get_chroma_collection()
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    @staticmethod
    def query_chroma(query_text: str, n_results: int = 30) -> Dict[str, Any]:
        """以語意向量查詢 ChromaDB 相似職缺。"""
        collection = get_chroma_collection()
        return collection.query(query_texts=[query_text], n_results=n_results)

    @staticmethod
    def get_starred_job_ids() -> List[str]:
        """取得所有已儲存在 SQLite starred_jobs 資料表的 job_id 清單。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id FROM starred_jobs ORDER BY created_at DESC")
            return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def toggle_star_job(job_id: str) -> Tuple[bool, int]:
        """在 SQLite 資料庫切換指定 job_id 的關注狀態，回傳 (is_starred, total_starred_count)。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM starred_jobs WHERE job_id = ?", (job_id,))
            exists = cursor.fetchone() is not None
            if exists:
                cursor.execute("DELETE FROM starred_jobs WHERE job_id = ?", (job_id,))
                is_starred = False
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO starred_jobs (job_id) VALUES (?)",
                    (job_id,),
                )
                is_starred = True
            conn.commit()

            cursor.execute("SELECT COUNT(*) FROM starred_jobs")
            total_count = cursor.fetchone()[0]
            return is_starred, total_count

    @staticmethod
    def is_job_starred(job_id: str) -> bool:
        """檢查特定職缺是否在 SQLite 中被標記為關注。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM starred_jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

