import json
from typing import Any, Dict, List, Optional
from database.connection import get_db_connection


class AnalysisRepository:
    """處理職缺深度分析 (job_deep_analysis) 的 CRUD 操作。"""

    @staticmethod
    def mark_latest_resume_outdated(user_id: str) -> None:
        """當使用者上傳新履歷時，將其所有深度分析標記為舊版 (is_latest_resume = 0)。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE job_deep_analysis SET is_latest_resume = 0 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()

    @staticmethod
    def get_analysis(user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """取得特定使用者與職缺的深度分析記錄。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT match_tech_score, match_exp_score, perfect_matches, fatal_gaps, 
                       hidden_strengths, hr_red_flags, resume_tweaks, interview_prep, 
                       cover_letter, is_latest_resume, updated_at
                FROM job_deep_analysis
                WHERE user_id = ? AND job_id = ?
                """,
                (user_id, job_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "match_tech_score": row[0] or 0,
                "match_exp_score": row[1] or 0,
                "perfect_matches": json.loads(row[2]) if row[2] else [],
                "fatal_gaps": json.loads(row[3]) if row[3] else [],
                "hidden_strengths": json.loads(row[4]) if row[4] else [],
                "hr_red_flags": json.loads(row[5]) if row[5] else [],
                "resume_tweaks": json.loads(row[6]) if row[6] else [],
                "interview_prep": json.loads(row[7]) if row[7] else [],
                "cover_letter": row[8],
                "is_latest_resume": row[9] if row[9] is not None else 1,
                "updated_at": row[10],
            }

    @staticmethod
    def upsert_analysis(
        user_id: str,
        job_id: str,
        match_tech_score: int,
        match_exp_score: int,
        perfect_matches: List[str],
        fatal_gaps: List[str],
        hidden_strengths: List[str],
        hr_red_flags: List[str],
        resume_tweaks: List[str],
    ) -> None:
        """新增或更新深度分析基礎結果。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO job_deep_analysis (
                    user_id, job_id, match_tech_score, match_exp_score,
                    perfect_matches, fatal_gaps, hidden_strengths, hr_red_flags,
                    resume_tweaks, is_latest_resume, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, job_id) DO UPDATE SET
                    match_tech_score = excluded.match_tech_score,
                    match_exp_score = excluded.match_exp_score,
                    perfect_matches = excluded.perfect_matches,
                    fatal_gaps = excluded.fatal_gaps,
                    hidden_strengths = excluded.hidden_strengths,
                    hr_red_flags = excluded.hr_red_flags,
                    resume_tweaks = excluded.resume_tweaks,
                    is_latest_resume = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    job_id,
                    match_tech_score,
                    match_exp_score,
                    json.dumps(perfect_matches, ensure_ascii=False),
                    json.dumps(fatal_gaps, ensure_ascii=False),
                    json.dumps(hidden_strengths, ensure_ascii=False),
                    json.dumps(hr_red_flags, ensure_ascii=False),
                    json.dumps(resume_tweaks, ensure_ascii=False),
                ),
            )
            conn.commit()

    @staticmethod
    def update_cover_letter(user_id: str, job_id: str, cover_letter: str) -> None:
        """更新自我推薦信至分析資料表。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO job_deep_analysis (user_id, job_id, cover_letter, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, job_id) DO UPDATE SET
                    cover_letter = excluded.cover_letter,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, job_id, cover_letter),
            )
            conn.commit()

    @staticmethod
    def update_interview_prep(
        user_id: str, job_id: str, interview_questions: List[Dict[str, Any]]
    ) -> None:
        """更新模擬面試題至分析資料表。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO job_deep_analysis (user_id, job_id, interview_prep, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, job_id) DO UPDATE SET
                    interview_prep = excluded.interview_prep,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    user_id,
                    job_id,
                    json.dumps(interview_questions, ensure_ascii=False),
                ),
            )
            conn.commit()
