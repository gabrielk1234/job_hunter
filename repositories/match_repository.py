import json
from typing import Any, Dict, List
from database.connection import get_db_connection


class MatchRepository:
    """處理職缺配對資料 (user_matches) 的 CRUD 操作。"""

    @staticmethod
    def delete_matches_by_user_id(user_id: str) -> None:
        """刪除指定使用者的所有既有配對紀錄。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_matches WHERE user_id = ?", (user_id,))
            conn.commit()

    @staticmethod
    def upsert_match(
        user_id: str,
        job_id: str,
        match_score: int,
        match_reasons: List[str],
        risk_reasons: List[str],
    ) -> None:
        """寫入或更新單筆使用者與職缺的配對分數與理由。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_matches (user_id, job_id, match_score, match_reasons, risk_reasons)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    job_id,
                    match_score,
                    json.dumps(match_reasons, ensure_ascii=False),
                    json.dumps(risk_reasons, ensure_ascii=False),
                ),
            )
            conn.commit()

    @staticmethod
    def get_matches_by_user_id(user_id: str) -> List[Dict[str, Any]]:
        """撈取使用者的職缺配對清單，依照匹配分數由高至低排序。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.job_id, m.match_score, m.match_reasons, m.risk_reasons, j.job_name, j.cust_name, j.job_link 
                FROM user_matches m
                JOIN job_documents j ON m.job_id = j.job_id
                WHERE m.user_id = ?
                ORDER BY m.match_score DESC
                """,
                (user_id,),
            )
            rows = cursor.fetchall()

            matches: List[Dict[str, Any]] = []
            for row in rows:
                match_reasons = []
                risk_reasons = []
                try:
                    if row[2]:
                        match_reasons = json.loads(row[2])
                    if row[3]:
                        risk_reasons = json.loads(row[3])
                except Exception:
                    pass

                matches.append(
                    {
                        "job_id": row[0],
                        "match_score": row[1],
                        "match_reasons": match_reasons,
                        "risk_reasons": risk_reasons,
                        "job_name": row[4],
                        "cust_name": row[5],
                        "job_link": row[6],
                    }
                )
            return matches
