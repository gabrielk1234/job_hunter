from typing import List, Optional
from pydantic import BaseModel


class ParsedProfileData(BaseModel):
    """解析後的結構化履歷內容。"""
    candidate_summary: str
    core_competencies: List[str]
    strengths: List[str]
    weaknesses_or_risks: List[str]
    recommended_roles: List[str]
    resume_advice: List[str]


class ProfileGetResponse(BaseModel):
    """取得履歷回應。"""
    status: str
    data: Optional[ParsedProfileData] = None
    message: Optional[str] = None


class ProfileParseResponse(BaseModel):
    """履歷健檢與解析回應。"""
    status: str
    data: Optional[ParsedProfileData] = None
    message: Optional[str] = None
