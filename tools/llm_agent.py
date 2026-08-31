from google import genai
from google.genai import types
from typing import List, Dict

import chromadb
import sqlite3
import json
import traceback
import textwrap

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

def search_jobs(query: str, filters: str = None, limit: int = 3) -> str:
    """
    用來搜尋職缺。
    
    :param query: 所有的「文字搜尋條件」，包含地點、職稱、技能。
                  (例如："高雄 韌體工程師"、"台北 軟體開發"、"React 前端")。
                  請把所有文字描述都塞在這裡，交給向量模型處理！
    :param filters: 這裡「只」用來過濾數字跟固定分類！嚴禁使用 $contains！
                    目前只能用這幾個欄位 (請嚴格遵守 dict 格式)：
                    - salaryMin (數字): 最低薪水要求。例如 {"salaryMin": {"$gte": 50000}}
                    - remoteWork (字串): 只能是 "無"、"部分遠端"、"完全遠端"。例如 {"remoteWork": {"$eq": "完全遠端"}}
                    - jobType (字串): 只能是 "全職"、"兼職"、"其他"。例如 {"jobType": {"$eq": "全職"}}
                    - salaryType (字串): "待遇面議"、"月薪"、"時薪"、"年薪"。例如 {"salaryType": {"$eq": "月薪"}}
                    
                    如果有兩個(含)以上的條件，請務必用 $and 包起來。
                    如果使用者沒有特別要求薪水或遠端等硬性條件，請直接留空 (None)。
    :param limit: 回傳的最大職缺數量，預設為 3。
    """
    if not collection:
        return "資料庫連線失敗，無法搜尋職缺。"
    
    if isinstance(filters, str):
        # 如果是字串，而且不是空的，就把它轉回 dict
        if filters.strip() != "":
            try:
                filters = json.loads(filters)
            except json.JSONDecodeError:
                print(f"解析 {filters} 失敗，直接當作沒有過濾條件")
                filters = None
        else:
            filters = None

    print(f"Gemini 正在使用工具搜尋：關鍵字='{query}', 條件={filters}")
    sqlite_db = 'all_jobs.db'
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    
    try:
        # 直接把 Gemini 組裝好的 filters 餵給 where
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=filters 
        )
        
        if not results['documents'][0]:
            print("沒有找到符合條件的職缺。")
            return "沒有找到符合條件的職缺。"

        # 將結果整理成文字回傳給 Gemini
        formatted_results = []
        job_id_set = set()
        for i in range(len(results['documents'][0])):
            doc = textwrap.dedent(results['documents'][0][i]) # 被切成chunk的資訊
            metadata = results['metadatas'][0][i]
            
            
            # ============== 找到chunk的原始片段
            job_id = metadata['job_id']
            
            if job_id in job_id_set: # 重複的chunk就不用撈原始資料了
                continue
            
            job_id_set.add(job_id)
            # 使用參數化查詢（?），避免 SQL Injection
            cursor.execute(
                "SELECT job_document FROM job_documents WHERE job_id = ?",
                (job_id,)
            )

            # 抓取單筆結果
            row = cursor.fetchone()

            if row:
                job_document = flatten(row[0])  # 取出第一個欄位 (job_document)
                print(job_document)
            else:
                print(f"找不到 ID 為 {job_id} 的職缺")
            
            job_info = f"""
            --- 職缺 {i+1} ---
            {job_document}
            """
            formatted_results.append(job_info)
            
        return "\n".join(formatted_results)
        
        
    except Exception as e:
        print(f"搜尋時發生錯誤: {str(e)}")
        return f"搜尋時發生錯誤: {str(e)}"

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
            請根據搜尋到的結果，用友善、有條理的方式向使用者推薦工作，並附上職缺連結。
            如果搜尋結果不符合使用者的期待，請溫柔地告知，並建議他們換個關鍵字搜尋。
            回答時可以適當使用 Markdown 格式（如粗體、條列式）來增加可讀性。
            
            注意：每次回答時，最多只能呼叫一次 search_jobs 工具，請精準下達篩選條件，不要重複搜尋！
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