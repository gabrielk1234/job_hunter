from typing import List, Optional
from pydantic import BaseModel


class MatchItem(BaseModel):
    """單筆職缺匹配卡片資料。"""
    job_id: str
    match_score: int
    match_reasons: List[str]
    risk_reasons: List[str]
    job_name: str
    cust_name: str
    job_link: Optional[str] = None


class MatchListResponse(BaseModel):
    """匹配結果列表回應。"""
    status: str
    data: List[MatchItem]
    message: Optional[str] = None


class MatchStatusData(BaseModel):
    """匹配引擎狀態資料。"""
    status: str
    progress: int
    log: str


class MatchStatusResponse(BaseModel):
    """匹配狀態回應。"""
    status: str
    data: MatchStatusData
    message: Optional[str] = None


class TriggerMatchResponse(BaseModel):
    """觸發背景匹配回應。"""
    status: str
    message: str
