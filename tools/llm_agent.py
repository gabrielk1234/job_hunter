from google import genai
from google.genai import types
from typing import Dict, Optional

import chromadb
import sqlite3
import json
import traceback

from tools.myown_tools import flatten

chroma_client = chromadb.PersistentClient(path="/Users/gkko/Documents/job_analysis/my_job_db")
try:
    collection = chroma_client.get_collection(name="job_chunks")
except Exception as e:
    print(f"無法載入 ChromaDB Collection: {e}")
    collection = None
    
active_chats: Dict[str, any] = {}

## 獲取API Key
with open('./apikey.json', 'r', encoding='utf-8') as f:
    api_key = json.load(f).get('gemini_api_key', '')

def _parse_filters(filters) -> Optional[dict]:
    if filters is None:
        return None
    if isinstance(filters, str):
        if filters.strip() == "":
            return None
        try:
            return json.loads(filters)
        except json.JSONDecodeError:
            print(f"解析 {filters} 失敗，直接當作沒有過濾條件")
            return None
    return filters


def _job_matches_location(metadata: dict, location: str) -> bool:
    """用地點關鍵字比對 metadata（address / jobName），不動資料庫內容。"""
    loc = location.strip()
    if not loc:
        return True
    address = metadata.get("address") or ""
    job_name = metadata.get("jobName") or ""
    return loc in address or loc in job_name


def search_jobs(
    query: str,
    filters: str = None,
    location: str = None,
    limit: int = 5,
) -> str:
    """
    用來搜尋職缺。

    :param query: 語意搜尋關鍵字，只放「職稱、技能、產業」等文字條件。
                  (例如："Unity 工程師"、"React 前端"、"韌體開發")。
                  請勿把地點放進 query，地點請用 location 參數！
    :param location: 工作地點關鍵字，用 metadata 的 address / jobName 做後篩。
                     (例如："高雄"、"台北"、"新竹")。
                     使用者沒有指定地點時留空。
    :param filters: 只用來過濾數字與固定分類（ChromaDB where），格式為 dict：
                    - salaryMin (數字): {"salaryMin": {"$gte": 50000}}
                    - remoteWork (字串): "無"、"部分遠端"、"完全遠端"
                    - jobType (字串): "全職"、"兼職"、"其他"
                    - salaryType (字串): "待遇面議"、"月薪"、"時薪"、"年薪"
                    多條件請用 $and 包起來；無硬性條件時留空。
    :param limit: 回傳的最大「職缺」數量（非 chunk 數），預設 3。
    """
    if not collection:
        return "資料庫連線失敗，無法搜尋職缺。"

    filters = _parse_filters(filters)
    location = (location or "").strip() or None

    # 向量搜尋先撈較多 chunk，再以 job_id 聚合，避免 top-3 chunk 被其他職缺佔滿
    pool_size = max(50, limit * 20)

    print(
        f"Gemini 正在使用工具搜尋：query='{query}', location='{location}', "
        f"filters={filters}, limit={limit}, pool_size={pool_size}"
    )

    sqlite_db = "all_jobs.db"
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()

    try:
        query_args = {"query_texts": [query], "n_results": pool_size}
        if filters:
            query_args["where"] = filters

        results = collection.query(**query_args)

        if not results["documents"][0]:
            print("沒有找到符合條件的職缺。")
            return "沒有找到符合條件的職缺。"

        # 依 job_id 聚合：同一職缺只保留相似度最高（distance 最小）的 chunk
        best_per_job: dict[str, tuple[float, dict]] = {}
        distances = results.get("distances") or [[]]

        for i, metadata in enumerate(results["metadatas"][0]):
            job_id = metadata.get("job_id")
            if not job_id:
                continue
            if location and not _job_matches_location(metadata, location):
                continue

            dist = distances[0][i] if distances[0] else float("inf")
            if job_id not in best_per_job or dist < best_per_job[job_id][0]:
                best_per_job[job_id] = (dist, metadata)

        if not best_per_job:
            hint = f"（已套用地點篩選：{location}）" if location else ""
            return f"沒有找到符合條件的職缺。{hint}"

        ranked_jobs = sorted(best_per_job.items(), key=lambda x: x[1][0])[:limit]

        formatted_results = []
        for rank, (job_id, (_, metadata)) in enumerate(ranked_jobs, start=1):
            cursor.execute(
                "SELECT job_document FROM job_documents WHERE job_id = ?",
                (job_id,),
            )
            row = cursor.fetchone()

            if row:
                job_document = flatten(row[0])
                print(f"[rank {rank}] job_id={job_id} {metadata.get('jobName')}")
            else:
                print(f"找不到 ID 為 {job_id} 的職缺")
                continue

            formatted_results.append(
                f"--- 職缺 {rank} ---\n"
                f"公司：{metadata.get('custName', '未知')}\n"
                f"職稱：{metadata.get('jobName', '未知')}\n"
                f"地址：{metadata.get('address', '未知')}\n"
                f"連結：{metadata.get('analysisUrl', '').replace('s/apply/analysis/', '/')}\n"
                f"{job_document}"
            )

        if not formatted_results:
            return "沒有找到符合條件的職缺。"

        return "\n\n".join(formatted_results)

    except Exception as e:
        print(f"搜尋時發生錯誤: {str(e)}")
        traceback.print_exc()
        return f"搜尋時發生錯誤: {str(e)}"
    finally:
        conn.close()

def ask_gemini(user_message: str, user_id: str = "default_user") -> str:
    """
    負責與 Gemini 溝通的核心函數, 用於有來有回的聊天機器人
    """
    if not api_key:
        return "系統錯誤：後端尚未設定 Gemini API Key！"

    try:
        # 1. 檢查這個使用者是否已經有開啟的對話 (記憶功能)
        if user_id not in active_chats:
            client = genai.Client(api_key=api_key)
            
            # 設定系統提示詞 (System Prompt)，賦予 AI 角色設定與工具指引
            system_instruction = """
            你是一位專業且熱情的 AI 職涯顧問 (JobHunter)。
            你的任務是協助使用者找到適合的職缺，並給予職涯建議。
            當使用者詢問職缺時，你「必須」使用 search_jobs 工具去資料庫查詢。

            【search_jobs 參數分工 — 請嚴格遵守】
            1. query：只放職稱、技能、框架、產業等語意關鍵字。
               ✅ 正確："Unity 工程師"、"React 前端"
               ❌ 錯誤："高雄 Unity"（地點不要放 query）
            2. location：使用者指定的地點，單獨傳入。
               例如使用者說「高雄」，location="高雄"；沒提到地點就留空。
            3. filters：只放結構化硬性條件（薪水、薪資類型、全職/兼職、遠端）。
               月薪 5 萬以上範例：{"$and": [{"salaryMin": {"$gte": 50000}}, {"salaryType": {"$eq": "月薪"}}]}
            4. limit：預設 3；使用者要更多結果時可調高。

            【範例】使用者問：「請找高雄，月薪 50000 以上，Unity 相關工作」
            → query="Unity 工程師", location="高雄",
              filters={"$and": [{"salaryMin": {"$gte": 50000}}, {"salaryType": {"$eq": "月薪"}}]}

            請根據搜尋結果，用友善、有條理的方式推薦工作，並附上職缺連結。
            若搜尋結果為空，可建議使用者放寬地點或薪資條件後再試。
            回答時可適當使用 Markdown 格式（粗體、條列式）。

            注意：每次回答最多只能呼叫一次 search_jobs，請一次帶齊所有條件。
            """
            
            # 建立具備 Tool 的對話 Session
            chat = client.chats.create(
                model='gemini-3.5-flash-lite',
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    tools=[search_jobs], 
                    temperature=0.3,
                )
            )
            active_chats[user_id] = {'client':client,
                                     'chat':chat}
        
        chat = active_chats[user_id]['chat']
        response = chat.send_message(user_message)
        
        return response.text
        
    except Exception as e:
        print(f"Gemini API 呼叫失敗: {str(e)}")
        return f"不好意思，我的大腦(API)暫時連線失敗了，錯誤訊息：{str(e)}"

def call_gemini(prompt:str,temperature:float =0.3,output_json=False):
    genai_client = genai.Client(api_key=api_key)
    if output_json:
        mime_type = "application/json"
    else:
        mime_type = None
    
    try:
        response = genai_client.models.generate_content(
                model='gemini-3.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type=mime_type, temperature=temperature)
            )
        return response
    except Exception as e:
        traceback.print_exc()
        print(f"tools/llm_agent (call_gemini)發生錯誤：{str(e)}")