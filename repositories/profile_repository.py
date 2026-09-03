import json
from typing import Any, Dict, Optional
from database.connection import get_db_connection


class ProfileRepository:
    """處理使用者履歷資料 (user_profiles) 的 CRUD 操作。"""

    @staticmethod
    def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """取得使用者的解析後履歷資料 (dict)。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT parsed_json FROM user_profiles WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return None
            return None

    @staticmethod
    def get_profile_raw(user_id: str) -> Optional[Dict[str, Any]]:
        """取得使用者的 raw_text 與 parsed_json 字串。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT raw_text, parsed_json FROM user_profiles WHERE user_id = ?",
                (user_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "raw_text": row[0],
                    "parsed_json": row[1],
                }
            return None

    @staticmethod
    def upsert_profile(user_id: str, raw_text: str, parsed_json_str: str) -> None:
        """新增或覆蓋使用者履歷資料。"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO user_profiles (user_id, raw_text, parsed_json)
                VALUES (?, ?, ?)
                """,
                (user_id, raw_text, parsed_json_str),
            )
            conn.commit()
