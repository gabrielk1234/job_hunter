import json
import traceback
from typing import Any, Dict, List
from repositories.job_repository import JobRepository
from repositories.match_repository import MatchRepository
from repositories.profile_repository import ProfileRepository
from tools.llm_agent import call_gemini


class MatchService:
    """處理 AI 職缺精準匹配引擎與背景排程商業邏輯。"""

    matching_status: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_status(cls, user_id: str) -> Dict[str, Any]:
        """取得特定使用者的配對進度與狀態。"""
        return cls.matching_status.get(
            user_id, {"status": "idle", "progress": 0, "log": ""}
        )

    @classmethod
    def get_matches(cls, user_id: str) -> List[Dict[str, Any]]:
        """取得指定使用者已配對計算完成的職缺卡片清單。"""
        return MatchRepository.get_matches_by_user_id(user_id)

    @classmethod
    def run_match_task(cls, user_id: str) -> None:
        """在背景執行的 AI 向量檢索與深度打分任務。"""
        cls.matching_status[user_id] = {
            "status": "running",
            "progress": 5,
            "log": "準備資料中...",
        }
        try:
            # 1. 刪除舊紀錄
            MatchRepository.delete_matches_by_user_id(user_id)

            # 2. 取得使用者履歷特徵
            profile = ProfileRepository.get_profile(user_id)
            if not profile:
                cls.matching_status[user_id] = {
                    "status": "error",
                    "progress": 0,
                    "log": "找不到履歷，請先至 Profile 上傳！",
                }
                return

            core_comp = ", ".join(profile.get("core_competencies", []))
            strengths = ", ".join(profile.get("strengths", []))
            query_str = f"尋找適合以下特質的職缺：精通 {core_comp}，優勢是 {strengths}"

            cls.matching_status[user_id] = {
                "status": "running",
                "progress": 15,
                "log": "透過 ChromaDB 向量檢索職缺中...",
            }

            # 3. ChromaDB 粗篩
            results = JobRepository.query_chroma(query_text=query_str, n_results=30)

            # 去重複的 job_id
            job_ids: List[str] = []
            if results.get("metadatas") and results["metadatas"][0]:
                for meta in results["metadatas"][0]:
                    if meta.get("job_id") and meta["job_id"] not in job_ids:
                        job_ids.append(meta["job_id"])

            top_job_ids = job_ids[:5]

            if not top_job_ids:
                cls.matching_status[user_id] = {
                    "status": "done",
                    "progress": 100,
                    "log": "找不到任何相關職缺",
                }
                return

            cls.matching_status[user_id] = {
                "status": "running",
                "progress": 30,
                "log": f"找到 {len(top_job_ids)} 筆潛在職缺，準備進行 AI 深度打分...",
            }

            for idx, j_id in enumerate(top_job_ids):
                job_row = JobRepository.get_job_by_id(j_id)
                if not job_row:
                    continue

                job_doc = job_row["job_document"]

                prompt = f"""
                你是一位嚴格的 HR。請比對以下候選人的履歷特徵與職缺內容，給出 0-100 的匹配分數。
                請嚴格輸出 JSON 格式，絕對不能包含其他文字：
                {{
                    "match_score": 85,
                    "match_reasons": ["符合條件1", "符合條件2"], 
                    "risk_reasons": ["潛在風險1"] 
                }}
                
                【候選人履歷特徵】：
                {json.dumps(profile, ensure_ascii=False)}
                
                【職缺內容】：
                {job_doc}
                """
                try:
                    response = call_gemini(
                        prompt=prompt, temperature=0.1, output_json=True
                    )

                    raw_text = response.text.strip()
                    if raw_text.startswith("```json"):
                        raw_text = raw_text[7:]
                    elif raw_text.startswith("```"):
                        raw_text = raw_text[3:]
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3]

                    score_data = json.loads(raw_text.strip())

                    MatchRepository.upsert_match(
                        user_id=user_id,
                        job_id=j_id,
                        match_score=score_data.get("match_score", 0),
                        match_reasons=score_data.get("match_reasons", []),
                        risk_reasons=score_data.get("risk_reasons", []),
                    )
                except Exception:
                    traceback.print_exc()

                current_prog = int(30 + ((idx + 1) / len(top_job_ids)) * 70)
                cls.matching_status[user_id] = {
                    "status": "running",
                    "progress": current_prog,
                    "log": f"AI 深度配對中... ({idx + 1}/{len(top_job_ids)})",
                }

            cls.matching_status[user_id] = {
                "status": "done",
                "progress": 100,
                "log": "配對完成！",
            }
        except Exception as e:
            traceback.print_exc()
            cls.matching_status[user_id] = {
                "status": "error",
                "progress": 0,
                "log": f"發生錯誤：{str(e)}",
            }
