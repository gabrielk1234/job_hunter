from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class JobMetadata(BaseModel):
    """職缺 Metadata 格式。"""
    job_id: Optional[str] = None
    jobName: Optional[str] = None
    custName: Optional[str] = None
    analysisUrl: Optional[str] = None
    custUrl: Optional[str] = "#"
    salaryType: Optional[str] = "未填寫"
    address: Optional[str] = "未提供"
    remoteWork: Optional[str] = "無"
    hrBehaviorPR: Optional[float] = 0.0
    lastProcessedResumeAtTime: Optional[int] = 0


class InterviewQuestionItem(BaseModel):
    """模擬面試題項目。"""
    type: str
    question: str
    advice: str


class DeepAnalysisData(BaseModel):
    """深度分析資料結構。"""
    match_tech_score: int
    match_exp_score: int
    perfect_matches: List[str]
    fatal_gaps: List[str]
    hidden_strengths: List[str]
    hr_red_flags: List[str]
    resume_tweaks: List[str]
    interview_prep: Optional[List[InterviewQuestionItem]] = []
    cover_letter: Optional[str] = None
    is_latest_resume: int = 1
    updated_at: Optional[str] = None


class DeepAnalysisResponse(BaseModel):
    """取得或執行深度分析之回應格式。"""
    status: str
    metadata: Optional[Dict[str, Any]] = None
    analysis: Optional[DeepAnalysisData] = None
    data: Optional[DeepAnalysisData] = None
    message: Optional[str] = None


class CoverLetterResponse(BaseModel):
    """自我推薦信回應。"""
    status: str
    data: Optional[str] = None
    message: Optional[str] = None


class InterviewQuestionsResponse(BaseModel):
    """模擬面試題回應。"""
    status: str
    data: Optional[List[InterviewQuestionItem]] = None
    message: Optional[str] = None
