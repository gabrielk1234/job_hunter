from fastapi import APIRouter, Form
from schemas.analysis import (
    CoverLetterResponse,
    DeepAnalysisData,
    DeepAnalysisResponse,
    InterviewQuestionItem,
    InterviewQuestionsResponse,
)
from services.analysis_service import AnalysisService

router = APIRouter(tags=["Analysis"])


@router.get("/api/get-deep-analysis", response_model=DeepAnalysisResponse)
def get_deep_analysis(user_id: str, job_id: str) -> DeepAnalysisResponse:
    """取得職缺深度分析結果與職缺 Metadata。"""
    try:
        result = AnalysisService.get_deep_analysis(
            user_id=user_id, job_id=job_id
        )
        status = result.get("status", "error")
        metadata = result.get("metadata")
        analysis_dict = result.get("analysis")

        analysis_obj = None
        if analysis_dict:
            prep_items = [
                InterviewQuestionItem(**q)
                for q in analysis_dict.get("interview_prep", [])
            ]
            analysis_dict["interview_prep"] = prep_items
            analysis_obj = DeepAnalysisData(**analysis_dict)

        return DeepAnalysisResponse(
            status=status,
            metadata=metadata,
            analysis=analysis_obj,
        )
    except Exception as e:
        return DeepAnalysisResponse(
            status="error",
            message=f"獲取深度分析失敗: {str(e)}",
        )


@router.post("/api/run-deep-analysis", response_model=DeepAnalysisResponse)
def run_deep_analysis(
    user_id: str = Form(...), job_id: str = Form(...)
) -> DeepAnalysisResponse:
    """執行目標職缺之深度健檢與多維度評分。"""
    try:
        data = AnalysisService.run_deep_analysis(user_id=user_id, job_id=job_id)
        prep_items = [
            InterviewQuestionItem(**q)
            for q in data.get("interview_prep", [])
        ]
        data["interview_prep"] = prep_items
        analysis_obj = DeepAnalysisData(**data)
        return DeepAnalysisResponse(status="success", data=analysis_obj)
    except Exception as e:
        return DeepAnalysisResponse(
            status="error", message=f"深度分析失敗: {str(e)}"
        )


@router.post("/api/generate-cover-letter", response_model=CoverLetterResponse)
def generate_cover_letter(
    user_id: str = Form(...), job_id: str = Form(...)
) -> CoverLetterResponse:
    """根據候選人履歷與職缺特色生成 104 自我推薦信。"""
    try:
        cover_letter = AnalysisService.generate_cover_letter(
            user_id=user_id, job_id=job_id
        )
        return CoverLetterResponse(status="success", data=cover_letter)
    except Exception as e:
        return CoverLetterResponse(status="error", message=str(e))


@router.post(
    "/api/generate-interview-questions",
    response_model=InterviewQuestionsResponse,
)
def generate_interview_questions(
    user_id: str = Form(...), job_id: str = Form(...)
) -> InterviewQuestionsResponse:
    """針對致命缺口與 HR 潛在顧慮生成模擬面試題與反殺策略。"""
    try:
        questions = AnalysisService.generate_interview_questions(
            user_id=user_id, job_id=job_id
        )
        items = [InterviewQuestionItem(**q) for q in questions]
        return InterviewQuestionsResponse(status="success", data=items)
    except Exception as e:
        return InterviewQuestionsResponse(status="error", message=str(e))
