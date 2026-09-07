import json
from typing import Any, Dict, Optional
from fastapi import UploadFile
import pymupdf
from google import genai
from google.genai import types

from repositories.analysis_repository import AnalysisRepository
from repositories.profile_repository import ProfileRepository


class ProfileService:
    """處理使用者履歷解析、深度健檢與特徵儲存商業邏輯。"""

    @staticmethod
    def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """取得已儲存的使用者履歷結構化資料。"""
        return ProfileRepository.get_profile(user_id)

    @staticmethod
    async def parse_and_save_profile(
        user_id: str,
        text: Optional[str] = None,
        file: Optional[UploadFile] = None,
    ) -> Dict[str, Any]:
        """讀取 PDF 或純文字履歷，呼叫 Gemini 進行結構化健檢分析並儲存至資料庫。"""
        resume_text = ""

        if file:
            if not file.filename.endswith(".pdf"):
                raise ValueError("只能上傳 PDF 檔案")

            content = await file.read()
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                for page in pdf:
                    extracted = page.get_text()
                    if extracted:
                        resume_text += extracted + "\n"
        elif text:
            resume_text = text
        else:
            raise ValueError("請提供檔案或文字內容")

        if len(resume_text.strip()) < 20:
            raise ValueError("履歷內容過短，無法解析")

        with open("./apikey.json", "r", encoding="utf-8") as f:
            api_key = json.load(f).get("gemini_api_key", "")

        client = genai.Client(api_key=api_key)

        prompt = f"""
        你是一位資深科技業獵頭與職涯顧問。請閱讀以下使用者的履歷，並對其進行「深度解讀與健檢」。
        不要只是重複履歷上的內容，我需要你給出專業的評價、分析他的市場競爭力，並指出潛在的風險。
        請嚴格按照指定的 JSON 格式回傳，絕對不要輸出 JSON 以外的任何文字！
        
        格式要求：
        {{
            "candidate_summary": "用 50 字以內精準總結該候選人的等級與核心定位 (例如：具備3年經驗的中階前端，擅長React但缺乏後端概念...)",
            "core_competencies": ["萃取出的核心競爭力1", "核心競爭力2"], // 真正有價值的賣點，限 3-5 項
            "strengths": ["履歷上的亮點/優勢1", "優勢2"],
            "weaknesses_or_risks": ["潛在弱點、HR可能會擔憂的點，或履歷寫得不清楚的地方1", "弱點2"],
            "recommended_roles": ["建議投遞的職缺方向1", "方向2"], // 例如：資深前端工程師、全端工程師
            "resume_advice": ["具體的履歷修改建議1", "建議2"] // 針對這份履歷怎麼寫會更好，給出具體操作建議
        }}
        
        履歷內容：
        {resume_text}
        """

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        parsed_data = json.loads(response.text)

        # 儲存至資料庫
        ProfileRepository.upsert_profile(
            user_id=user_id,
            raw_text=resume_text,
            parsed_json_str=json.dumps(parsed_data, ensure_ascii=False),
        )

        # 標記先前深度分析為舊版履歷
        AnalysisRepository.mark_latest_resume_outdated(user_id=user_id)

        return parsed_data
