import sqlite3
import chromadb
from typing import Generator
from contextlib import contextmanager

SQLITE_DB_PATH = "all_jobs.db"
CHROMA_DB_PATH = "./my_job_db"
CHROMA_COLLECTION_NAME = "job_chunks"


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """獲取 SQLite 資料庫連線的 Context Manager。"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_chroma_collection(collection_name: str = CHROMA_COLLECTION_NAME):
    """獲取 ChromaDB 的 PersistentClient 與指定 Collection。"""
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return client.get_or_create_collection(name=collection_name)


def init_db() -> None:
    """初始化 SQLite 資料表結構。"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS job_documents (
                job_id TEXT PRIMARY KEY,
                job_document TEXT,
                job_name TEXT,
                cust_name TEXT,
                job_link TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                raw_text TEXT,
                parsed_json TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_matches (
                user_id TEXT,
                job_id TEXT,
                match_score INTEGER,
                match_reasons TEXT,
                risk_reasons TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, job_id)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS job_deep_analysis (
                user_id TEXT,
                job_id TEXT,
                match_tech_score INTEGER,
                match_exp_score INTEGER,
                perfect_matches TEXT,
                fatal_gaps TEXT,
                hidden_strengths TEXT,
                hr_red_flags TEXT,
                resume_tweaks TEXT,
                interview_prep TEXT,
                cover_letter TEXT,
                is_latest_resume INTEGER DEFAULT 1,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, job_id)
            )
            """
        )
        conn.commit()
