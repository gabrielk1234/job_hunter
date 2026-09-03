from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database.connection import init_db
from routers import (
    analysis_router,
    chat_router,
    jobs_router,
    matching_router,
    profile_router,
    scraper_router,
    views_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理：啟動時自動初始化資料庫表格。"""
    init_db()
    yield


app = FastAPI(
    title="JobHunter API",
    description="基於分層式架構 (Layered Architecture) 的 AI 職缺分析與健檢系統",
    version="1.0.0",
    lifespan=lifespan,
)

# 設定 CORS 通行證
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 掛載靜態檔案目錄
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# 註冊所有 API Routers 與 Views
app.include_router(views_router)
app.include_router(jobs_router)
app.include_router(scraper_router)
app.include_router(profile_router)
app.include_router(chat_router)
app.include_router(matching_router)
app.include_router(analysis_router)