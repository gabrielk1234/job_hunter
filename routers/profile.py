from typing import Optional
from fastapi import APIRouter, File, Form, UploadFile
from schemas.profile import (
    ParsedProfileData,
    ProfileGetResponse,
    ProfileParseResponse,
)
from services.profile_service import ProfileService

router = APIRouter(tags=["Profile"])


@router.get("/api/get-profile", response_model=ProfileGetResponse)
def get_profile(user_id: str) -> ProfileGetResponse:
    """取得現有的結構化履歷資料，供前端頁面載入時渲染。"""
    profile_data = ProfileService.get_profile(user_id=user_id)
    if profile_data:
        return ProfileGetResponse(
            status="success", data=ParsedProfileData(**profile_data)
        )
    return ProfileGetResponse(status="error", message="找不到資料")


@router.post("/api/parse-profile", response_model=ProfileParseResponse)
async def parse_profile(
    user_id: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> ProfileParseResponse:
    """接收上傳之 PDF 檔案或純文字履歷，呼叫 Gemini 進行深度解讀並存入資料庫。"""
    try:
        parsed_data = await ProfileService.parse_and_save_profile(
            user_id=user_id, text=text, file=file
        )
        return ProfileParseResponse(
            status="success", data=ParsedProfileData(**parsed_data)
        )
    except Exception as e:
        return ProfileParseResponse(status="error", message=str(e))
