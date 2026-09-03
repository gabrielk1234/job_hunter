from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["Views"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def get_home(request: Request) -> HTMLResponse:
    """首頁。"""
    return templates.TemplateResponse(
        request=request, name="home.html", context={"active_page": "home"}
    )


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard(request: Request) -> HTMLResponse:
    """職缺資料總覽與 SQLite / ChromaDB 儀表板頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"active_page": "dashboard"},
    )


@router.get("/scrapper", response_class=HTMLResponse)
def get_scrapper(request: Request) -> HTMLResponse:
    """104 職缺即時爬蟲任務控制器頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="scrapper.html",
        context={"active_page": "scrapper"},
    )


@router.get("/profile", response_class=HTMLResponse)
def get_profile_page(request: Request) -> HTMLResponse:
    """履歷上傳與深度健檢報告頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={"active_page": "profile"},
    )


@router.get("/assistant", response_class=HTMLResponse)
def get_assistant(request: Request) -> HTMLResponse:
    """AI 職涯顧問對話助理頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="assistant.html",
        context={"active_page": "assistant"},
    )


@router.get("/matches", response_class=HTMLResponse)
def get_matches_page(request: Request) -> HTMLResponse:
    """AI 精準職缺配對卡片頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="matches.html",
        context={"active_page": "matches"},
    )


@router.get("/analysis", response_class=HTMLResponse)
def get_analysis_page(request: Request) -> HTMLResponse:
    """職缺深度分析與面試實戰模擬頁面。"""
    return templates.TemplateResponse(
        request=request,
        name="analysis.html",
        context={"active_page": "dashboard"},
    )
