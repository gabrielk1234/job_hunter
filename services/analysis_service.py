import json
from typing import Any, Dict, List, Optional
from repositories.analysis_repository import AnalysisRepository
from repositories.job_repository import JobRepository
from repositories.profile_repository import ProfileRepository
from tools.llm_agent import call_gemini


class AnalysisService:
    """處理職缺深度健檢、Cover Letter 與模擬面試題生成的商業邏輯。"""

    @staticmethod
    def get_deep_analysis(user_id: str, job_id: str) -> Dict[str, Any]:
        """撈取職缺 Metadata 與使用者的深度分析結果。"""
        metadata: Dict[str, Any] = {}
        try:
            chroma_meta = JobRepository.get_chroma_metadata_by_id(job_id)
            if chroma_meta:
                metadata = chroma_meta
        except Exception:
            pass

        # 若 ChromaDB 沒抓到，嘗試從 SQLite 補齊基礎資料
        if not metadata or not metadata.get("jobName"):
            job_row = JobRepository.get_job_by_id(job_id)
            if job_row:
                metadata = {
                    "job_id": job_id,
                    "jobName": job_row["job_name"],
                    "custName": job_row["cust_name"],
                    "analysisUrl": job_row["job_link"] or "",
                    "custUrl": "#",
                    "salaryType": "未填寫",
                    "address": "未提供",
                    "remoteWork": "無",
                    "hrBehaviorPR": 0.0,
                    "lastProcessedResumeAtTime": 0,
                }

        analysis = AnalysisRepository.get_analysis(user_id=user_id, job_id=job_id)
        if analysis:
            return {
                "status": "success",
                "metadata": metadata,
                "analysis": analysis,
            }
        return {
            "status": "not_analyzed",
            "metadata": metadata,
        }

    @staticmethod
    def run_deep_analysis(user_id: str, job_id: str) -> Dict[str, Any]:
        """執行 Gemini 職缺與履歷多維度深度匹配分析。"""
        profile_raw = ProfileRepository.get_profile_raw(user_id)
        if not profile_raw:
            raise ValueError("找不到履歷資料，請先至 Profile 頁面上傳履歷！")

        user_profile_json = profile_raw["parsed_json"]

        job_row = JobRepository.get_job_by_id(job_id)
        if not job_row:
            raise ValueError("找不到該職缺的完整資料！")

        job_document = job_row["job_document"]

        prompt = f"""
        你是一位資深科技業獵頭與技術主管。請根據以下候選人的【履歷特徵】與【目標職缺說明】，進行極度精準、客觀且深度的職缺匹配與履歷健檢。
        
        請嚴格按照指定的 JSON 格式回傳，絕對不要輸出任何 JSON 以外的文字：
        {{
            "match_tech_score": 75, // 0-100 的整數，硬技術吻合度評分
            "match_exp_score": 85,  // 0-100 的整數，經歷/年資/產業吻合度評分
            "perfect_matches": [
                "候選人完全命中或超出要求的技能/條件1",
                "條件2"
            ],
            "hidden_strengths": [
                "候選人具備但履歷未充分突顯的隱藏實力或加分亮點1",
                "亮點2"
            ],
            "fatal_gaps": [
                "職缺硬性要求但候選人明顯欠缺的致命技能缺口1",
                "缺口2"
            ],
            "hr_red_flags": [
                "HR 或面試官審視履歷時可能產生的質疑、顧慮或扣分點1",
                "顧慮2"
            ],
            "resume_tweaks": [
                "針對此職缺的具體履歷修改與排版微調建議1",
                "建議2"
            ]
        }}

        【候選人履歷特徵】：
        {user_profile_json}

        【職缺說明】：
        {job_document}
        """

        response = call_gemini(prompt=prompt, temperature=0.2, output_json=True)
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        analysis_data = json.loads(raw_text.strip())

        AnalysisRepository.upsert_analysis(
            user_id=user_id,
            job_id=job_id,
            match_tech_score=int(analysis_data.get("match_tech_score", 0)),
            match_exp_score=int(analysis_data.get("match_exp_score", 0)),
            perfect_matches=analysis_data.get("perfect_matches", []),
            fatal_gaps=analysis_data.get("fatal_gaps", []),
            hidden_strengths=analysis_data.get("hidden_strengths", []),
            hr_red_flags=analysis_data.get("hr_red_flags", []),
            resume_tweaks=analysis_data.get("resume_tweaks", []),
        )

        updated_analysis = AnalysisRepository.get_analysis(user_id, job_id) or {}

        return {
            "match_tech_score": int(analysis_data.get("match_tech_score", 0)),
            "match_exp_score": int(analysis_data.get("match_exp_score", 0)),
            "perfect_matches": analysis_data.get("perfect_matches", []),
            "fatal_gaps": analysis_data.get("fatal_gaps", []),
            "hidden_strengths": analysis_data.get("hidden_strengths", []),
            "hr_red_flags": analysis_data.get("hr_red_flags", []),
            "resume_tweaks": analysis_data.get("resume_tweaks", []),
            "interview_prep": updated_analysis.get("interview_prep", []),
            "cover_letter": updated_analysis.get("cover_letter"),
            "is_latest_resume": 1,
            "updated_at": updated_analysis.get("updated_at"),
        }

    @staticmethod
    def generate_cover_letter(user_id: str, job_id: str) -> str:
        """根據履歷特徵與職缺內容生成 104 自我推薦信。"""
        profile_raw = ProfileRepository.get_profile_raw(user_id)
        if not profile_raw:
            raise ValueError("找不到履歷資料，請先上傳履歷")
        user_profile = profile_raw["parsed_json"]

        job_row = JobRepository.get_job_by_id(job_id)
        if not job_row:
            raise ValueError("找不到該職缺的完整資料")
        job_document = job_row["job_document"]

        prompt = f"""
        你是一位求職專家。請根據以下候選人的「履歷特徵」與「職缺完整說明」，幫他撰寫一封要在 104 人力銀行投遞時使用的「自我推薦信 (Cover Letter)」。
        
        【寫作要求】：
        1. 字數控制在 150-250 字之間，適合在網頁閱讀。分段要明確。
        2. 語氣要專業、自信但不自傲，展現對該職缺的熱情。
        3. 必須精準抓出候選人身上「最符合該職缺」的技能或經歷，直接命中 HR 的痛點。
        
        【輸出格式】：
        請嚴格輸出 JSON 格式，格式如下：
        {{
            "cover_letter": "這裡填寫推薦信內容，段落之間請用換行符號分隔"
        }}

        【候選人履歷特徵】：
        {user_profile}
        
        【職缺完整說明】：
        {job_document}
        """

        response = call_gemini(prompt=prompt, temperature=0.4, output_json=True)
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        parsed_json = json.loads(raw_text.strip())
        letter_text = parsed_json.get("cover_letter", "生成推薦信失敗，請重試。")

        AnalysisRepository.update_cover_letter(user_id, job_id, letter_text)
        return letter_text

    @staticmethod
    def generate_interview_questions(
        user_id: str, job_id: str
    ) -> List[Dict[str, Any]]:
        """針對技能缺口與 HR 顧慮生成模擬面試題與反殺策略。"""
        analysis = AnalysisRepository.get_analysis(user_id, job_id)
        fatal_gaps = "無特定技能缺口"
        hr_red_flags = "無特定風險顧慮"
        if analysis:
            if analysis.get("fatal_gaps"):
                fatal_gaps = json.dumps(
                    analysis["fatal_gaps"], ensure_ascii=False
                )
            if analysis.get("hr_red_flags"):
                hr_red_flags = json.dumps(
                    analysis["hr_red_flags"], ensure_ascii=False
                )

        job_row = JobRepository.get_job_by_id(job_id)
        job_document = job_row["job_document"] if job_row else ""

        prompt = f"""
        你是一位具備多年經驗的資深技術主管與嚴格面試官。
        請針對以下候選人面對此職缺時所暴露的「致命技能缺口 (fatal gaps)」與「HR 潛在挑剔點 (red flags)」，
        模擬面試情境，產出 2 題最具殺傷力與代表性的關鍵面試題目，並為求職者提供具體、高 EQ 且具說服力的「反殺策略 (回答建議)」。

        【缺口與風險點】：
        - 致命技能缺口：{fatal_gaps}
        - HR 潛在挑剔點：{hr_red_flags}

        【職缺說明】：
        {job_document}

        【輸出格式】：
        請嚴格按照以下 JSON Array 格式回傳 2 題面試題，絕對不要輸出任何 JSON 以外的文字：
        [
            {{
                "type": "分類標籤 (例如：情境挑戰、履歷挖洞預警、技術深挖、壓力測試)",
                "question": "面試官會問的具體問題",
                "advice": "求職者的反殺策略與回答思路建議"
            }},
            {{
                "type": "分類標籤 (例如：情境挑戰、履歷挖洞預警、技術深挖、壓力測試)",
                "question": "面試官會問的具體問題",
                "advice": "求職者的反殺策略與回答思路建議"
            }}
        ]
        """

        response = call_gemini(prompt=prompt, temperature=0.3, output_json=True)
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        interview_questions = json.loads(raw_text.strip())
        AnalysisRepository.update_interview_prep(
            user_id, job_id, interview_questions
        )
        return interview_questions
