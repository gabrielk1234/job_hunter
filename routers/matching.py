from fastapi import APIRouter, BackgroundTasks, Form
from schemas.match import (
    MatchItem,
    MatchListResponse,
    MatchStatusData,
    MatchStatusResponse,
    TriggerMatchResponse,
)
from services.match_service import MatchService

router = APIRouter(tags=["Matching"])


@router.post("/api/trigger-match", response_model=TriggerMatchResponse)
def trigger_match(
    background_tasks: BackgroundTasks, user_id: str = Form(...)
) -> TriggerMatchResponse:
    """觸發背景 AI 職缺配對任務。"""
    background_tasks.add_task(MatchService.run_match_task, user_id)
    return TriggerMatchResponse(status="success", message="已開始背景配對")


@router.get("/api/match-status", response_model=MatchStatusResponse)
def get_match_status(user_id: str) -> MatchStatusResponse:
    """提供前端輪詢查詢當前配對進度與狀態。"""
    status_dict = MatchService.get_status(user_id=user_id)
    return MatchStatusResponse(
        status="success", data=MatchStatusData(**status_dict)
    )


@router.get("/api/get-matches", response_model=MatchListResponse)
def get_matches(user_id: str) -> MatchListResponse:
    """取得特定使用者所有已完成配對的職缺卡片清單。"""
    try:
        matches = MatchService.get_matches(user_id=user_id)
        items = [MatchItem(**m) for m in matches]
        return MatchListResponse(status="success", data=items)
    except Exception as e:
        return MatchListResponse(status="error", data=[], message=str(e))
