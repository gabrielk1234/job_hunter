from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request,Form,File,UploadFile,FastAPI,WebSocket, WebSocketDisconnect,BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types

import asyncio
import sqlite3
import requests
import json
import chromadb
import traceback
import fitz
import math
import browser_cookie3

from tools.myown_tools import flatten
from tools.llm_agent import call_gemini,ask_gemini

# 定義接收前端資料的格式 (Pydantic 模型)
class ChatRequest(BaseModel):
    message: str

app = FastAPI(title="JobHunter API")
# 告訴 FastAPI 你的模板放在哪裡
templates = Jinja2Templates(directory="templates")
# 設定 CORS 通行證，允許前端網頁連線
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開發階段允許所有來源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def init_db():
    sqlite_db = 'all_jobs.db'
    conn = sqlite3.connect(sqlite_db)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_documents (
            job_id TEXT PRIMARY KEY,
            job_document TEXT,
            job_name TEXT,
            cust_name TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id TEXT PRIMARY KEY,
            raw_text TEXT,
            parsed_json TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_matches (
            user_id TEXT,
            job_id TEXT,
            match_score INTEGER,
            match_reasons TEXT,
            risk_reasons TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, job_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_deep_analysis (
            user_id TEXT,
            job_id TEXT,
            match_tech_score INTEGER,
            match_exp_score INTEGER,
            perfect_matches TEXT,
            fatal_gaps TEXT,
            hidden_strengths TEXT,
            hr_red_flags TEXT,
            resume_tweaks TEXT,
            interview_prep TEXT,
            cover_letter TEXT,
            is_latest_resume INTEGER DEFAULT 1,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, job_id)
        )
    ''')
    conn.commit()
    conn.close()

init_db() # 啟動 API 時先建立表格

@app.get("/api/sqlite-jobs")
def get_sqlite_jobs(page: int = 1, limit: int = 20,keyword:str=""):
    """從 SQLite 撈取原始職缺 JSON 資料"""
    try:
        # 連線到你的 SQLite 資料庫 (檔名請確認跟爬蟲存的一樣)
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        
        # SQL條件與參數
        where_clause = ""
        search_params = ()
        
        if keyword:
            where_clause = " WHERE job_id LIKE ? OR cust_name LIKE ? OR job_name LIKE ?"
            like_kw = f"%{keyword}%"
            search_params = (like_kw, like_kw, like_kw)
        
        # 先算總共有幾筆資料
        count_query = f"SELECT COUNT(*) FROM job_documents{where_clause}"
        cursor.execute(count_query, search_params)
        total_count = cursor.fetchone()[0]
        
        # 計算位移量
        offset = (page - 1) * limit
        
        # 撈取當前頁面的資料
        select_query = f"SELECT job_id, job_document, job_name, cust_name, job_link FROM job_documents{where_clause} LIMIT ? OFFSET ?"
        final_params = search_params + (limit, offset)
        cursor.execute(select_query, final_params)
        rows = cursor.fetchall()
        
        jobs = []
        for row in rows:
            job_id, job_data_str, job_name, cust_name, job_link = row
            try:
                jobs.append({
                    "job_id": job_id,
                    "custName": cust_name,
                    "jobName": job_name,
                    "raw_json": flatten(job_data_str),
                    "job_link":job_link
                })
            except Exception as e:
                print(f"解析 JSON 失敗 ID: {job_id}")
                
        return {
            "status": "success", 
            "data": jobs, 
            "total": total_count,
            "page": page,
            "total_pages": math.ceil(total_count / limit) if total_count > 0 else 1}
    except Exception as e:
        return {"status": "error", "message": f"SQLite 連線錯誤: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/chroma-jobs")
def get_chroma_jobs(page: int = 1, limit: int = 20, min_salary: int = 0, min_hr_pr: float = 0.0,keyword:str=""):
    """從 ChromaDB 撈取向量化後的 Metadata 與 Documents"""
    try:
        # 連線到本機的 ChromaDB 資料夾
        client = chromadb.PersistentClient(path="./my_job_db")
        collection = client.get_collection(name="job_chunks")
        
        offset = (page - 1) * limit
        
        # 組合 ChromaDB 的過濾條件 (where clause)
        conditions = []
        if min_salary > 0:
            if min_salary <= 40000:
                conditions.append({"salaryMin": {"$gte": min_salary}})
            else:
                conditions.append({
                    "$or": [
                        {"salaryMin": {"$gte": min_salary}},
                        {"salaryMin": {"$eq": 0}}
                    ]
                })
                
        if min_hr_pr > 0:
            # 強制轉成 float 確保型態正確
            conditions.append({"hrBehaviorPR": {"$gte": float(min_hr_pr)}})
            
        if keyword:
            conditions.append({
                "$or": [
                    {"job_id": {"$contains": keyword}},
                    {"jobName": {"$contains": keyword}},
                    {"custName": {"$contains": keyword}}
                ]
            })
            
        where_clause = None
        if len(conditions) == 1:
            where_clause = conditions[0]
        elif len(conditions) > 1:
            where_clause = {"$and": conditions}

        # === Debug 用的 Print ===
        print(f"🕵️ [Debug] 前端傳過來的參數 -> 薪資: {min_salary} (type: {type(min_salary)}), PR: {min_hr_pr} (type: {type(min_hr_pr)})")
        print(f"🕵️ [Debug] 丟給 Chroma 的條件 -> {where_clause}")
            
        # 準備查詢參數
        query_args = {
            "limit": limit,
            "offset": offset
        }
        if where_clause:
            query_args["where"] = where_clause
            
        results = collection.get(**query_args)
        
        # ChromaDB 比較難直接算篩選後的總數，我們給個大概或是回傳當前抓到的總數
        total_in_db = collection.count()
        
        jobs = []
        if results and results.get('ids'):
            for i in range(len(results['ids'])):
                jobs.append({
                    "id": results['ids'][i],
                    "metadata": results['metadatas'][i] if results['metadatas'] else {},
                    "document": results['documents'][i] if results['documents'] else ""
                })
        return {
            "status": "success", 
            "data": jobs, 
            "total_in_db": total_in_db, # 這是整個資料庫的總數，不是篩選後的
            "page": page,
            "total_pages":math.ceil(total_in_db / limit) if total_in_db > 0 else 1,
        }
    except Exception as e:
        return {"status": "error", "message": f"ChromaDB 連線錯誤: {str(e)}"}
    
@app.websocket("/api/ws-scrape")
async def websocket_scrape(websocket: WebSocket):
    # 接起前端打來的「電話」
    await websocket.accept()
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        # 1. 接收前端傳來的 JSON 參數
        data = await websocket.receive_json()
        areas = data.get("areas", [])
        jobcats = data.get("jobcats", [])
        keywordInput = data.get("keyword","")
        
        await websocket.send_json({"log": "🕸️ WebSocket 連線成功，背景爬蟲任務開始執行！", "progress": 2})
        
        # 讀取設定檔與連線資料庫
        config_file = './config.json'
        table_name = 'job_documents'
        chroma_db = './my_job_db'
        chroma_collection = 'job_chunks'

        with open(config_file, 'r', encoding='utf-8') as f:
            config_json = json.load(f)
        headers = config_json['headers']
        cookies = browser_cookie3.chrome(domain_name='104.com.tw',cookie_file=r"/Users/gkko/Library/Application Support/Google/Chrome/Profile 13/Cookies")

        client = chromadb.PersistentClient(path=chroma_db)
        collection = client.get_or_create_collection(name=chroma_collection)
        await websocket.send_json({"log": "✅ 資料庫連線完成", "progress": 5})

        area_str = ",".join(areas)
        jobcat_str = ",".join(jobcats)
        await websocket.send_json({"log": f"設定條件為:關鍵字:{keywordInput}", "progress": 8})
    
        params = {
            'keyword':keywordInput,
            'area': area_str,
            'jobcat': jobcat_str,
            'jobsource': 'joblist_search',
            'mode': 's',
            'orLabel': 'foreigners@overseasStudents^20,foreigners@chineseDiasporas^20',
            'order': '16',
            'page': '1',
            'pagesize': '20',
        }

        await websocket.send_json({"log": "🔍 正在向 104 請求職缺列表...", "progress": 10})
        
        # 💡 重要：使用 asyncio.to_thread 讓 requests.get 不會卡死這通 WebSocket 電話
        response = await asyncio.to_thread(requests.get, 'https://www.104.com.tw/jobs/search/api/jobs', params=params, cookies=cookies, headers=headers)
        
        if response.status_code != 200:
            await websocket.send_json({"log": "❌ 無法獲取列表，可能是 Cookie 過期或是被擋了", "done": True})
            return

        job_json = response.json()['data']
        total_jobs = len(job_json)
        
        if total_jobs == 0:
            await websocket.send_json({"log": "⚠️ 找不到符合條件的職缺喔！", "progress": 100, "done": True})
            return

        await websocket.send_json({"log": f"📊 共找到 {total_jobs} 個職缺，準備開始抓取細節！", "progress": 15})

        import random as rd
        from tools.pharse import get_document, get_metadata,create_chunks

        for idx, job in enumerate(job_json, 1):
            job_id = job['jobNo']
            job_code = job['link']['job'].split('/')[-1]
            cust_name = job.get('custName', '未知公司')

            await websocket.send_json({"log": f"➤ [{idx}/{total_jobs}] 正在抓取：{cust_name} - {job_code}..."})

            job_detail_response = await asyncio.to_thread(requests.get, f'https://www.104.com.tw/api/jobs/{job_code}', cookies=cookies, headers=headers)
            
            if job_detail_response.status_code == 200:
                job_detail_json = job_detail_response.json().get('data')
                
                # ChromaDB 儲存
                documents = get_document(job_detail_json)
                metadata = get_metadata(job_detail_json)
                chunks = create_chunks(job_id=job_id,full_document=documents,base_metadata=metadata)
                
                chunk_ids = [str(c['ids']) for c in chunks]
                chunk_documents = [c['text'] for c in chunks]
                chunk_metadatas = [c['metadata'] for c in chunks]
                collection.add(
                    documents=chunk_documents, 
                    metadatas=chunk_metadatas, 
                    ids=chunk_ids
                )
                
                # SQLite 儲存
                job_name = metadata['jobName']
                cust_name = metadata['custName']
                job_link = metadata['analysisUrl'].replace('s/apply/analysis/','/')
                cursor.execute(f'''
                    INSERT OR REPLACE INTO {table_name} (job_id, job_document,job_name,cust_name,job_link) 
                    VALUES (?, ?, ?, ?,?)
                ''', (job_id, documents,job_name,cust_name,job_link))
                conn.commit()
                
                # 計算即時進度比例
                progress_percent = int(15 + (idx / total_jobs) * 85)
                await websocket.send_json({"log": f"  └─ ✅ 成功存入：{job_id}", "progress": progress_percent})
            else: 
                await websocket.send_json({"log": f"  └─ ❌ {job_code} 獲取資料失敗！"})
            
            # 💡 重要：這裡必須用 asyncio.sleep 而不是 time.sleep，才能讓訊息實時推出去
            sleep_time = rd.randint(2, 5)
            await websocket.send_json({"log": f"  └─ ⏳ 休息 {sleep_time} 秒以防被封鎖..."})
            await asyncio.sleep(sleep_time)

        await websocket.send_json({"log": "🎉 爬蟲任務全部完工！", "progress": 100, "done": True})

    except WebSocketDisconnect:
        print("前端斷開連線")
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"【系統異常】\n{error_trace}")
        error_type = type(e).__name__
        await websocket.send_json({
            "log": f"❌ 致命錯誤 [{error_type}]: {str(e)}。詳細報錯請看後端終端機！", 
            "done": True
        })
        
@app.get("/api/get-profile")
def get_profile(user_id: str):
    """取得現有的履歷資料，供頁面載入時顯示"""
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        cursor.execute("SELECT parsed_json FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"status": "success", "data": json.loads(row[0])}
        return {"status": "error", "message": "找不到資料"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    # 從 config 中抓取 API Key
    try:
        # 呼叫我們的獨立模組
        reply = ask_gemini(user_message=req.message)
        
        return {"status": "success", "reply": reply}
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"【系統異常】\n{error_trace}")
        return {"status": "error", "reply": f"系統發生錯誤：{str(e)}"}
    
@app.post("/api/parse-profile")
async def parse_profile(
    user_id: str = Form(...),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        resume_text = ""
        
        # 1. 處理輸入來源 (PDF 或純文字)
        if file:
            if not file.filename.endswith('.pdf'):
                return {"status": "error", "message": "只能上傳 PDF 檔案"}
            
            # 使用 pdfplumber 讀取上傳的 PDF 檔案
            with fitz.open(stream=file.file.read(),filetype='pdf') as pdf:
                for page in pdf:
                    extracted = page.get_text()
                    if extracted:
                        resume_text += extracted + "\n"
        elif text:
            resume_text = text
        else:
            return {"status": "error", "message": "請提供檔案或文字內容"}

        if len(resume_text.strip()) < 20:
            return {"status": "error", "message": "履歷內容過短，無法解析"}

        print(resume_text)
        
        # 2. 呼叫 Gemini 進行結構化解析 (強制輸出 JSON)
        with open('./apikey.json', 'r', encoding='utf-8') as f:
            api_key = json.load(f).get('gemini_api_key', '')
            
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
            model='gemini-3.5-flash-lite',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", # 強制要求模型回傳合法的 JSON
                temperature=0.1
            )
        )
        
        parsed_data = json.loads(response.text)
        
        # 3. 存入 SQLite 資料庫
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_profiles (user_id, raw_text, parsed_json)
            VALUES (?, ?, ?)
        ''', (user_id, resume_text, json.dumps(parsed_data, ensure_ascii=False)))
        
        # 將job_deep_analysis中的is_latest_resume設爲false
        cursor.execute("UPDATE job_deep_analysis SET is_latest_resume = 0 WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "data": parsed_data}
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(error_trace)
        return {"status": "error", "message": str(e)}



matching_status = {}
def run_match_task(user_id: str):
    """在背景執行的 AI 配對引擎"""
    matching_status[user_id] = {"status": "running", "progress": 5, "log": "準備資料中..."}
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        
        # 1. 刪除舊紀錄 (因為履歷可能更新了)
        cursor.execute("DELETE FROM user_matches WHERE user_id = ?", (user_id,))
        conn.commit()
        
        # 2. 取得使用者履歷特徵
        cursor.execute("SELECT parsed_json FROM user_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            matching_status[user_id] = {"status": "error", "progress": 0, "log": "找不到履歷，請先至 Profile 上傳！"}
            return
        
        profile = json.loads(row[0])
        core_comp = ", ".join(profile.get('core_competencies', []))
        strengths = ", ".join(profile.get('strengths', []))
        query_str = f"尋找適合以下特質的職缺：精通 {core_comp}，優勢是 {strengths}"
        print(f"丟入ChromaDB向量資料庫搜索,prompt如下:\n{query_str}")
        matching_status[user_id] = {"status": "running", "progress": 15, "log": "透過 ChromaDB 向量檢索職缺中..."}
        
        # 3. ChromaDB 粗篩
        client = chromadb.PersistentClient(path="./my_job_db")
        collection = client.get_collection(name="job_chunks")
        results = collection.query(query_texts=[query_str], n_results=30)
        
        # 去重複的 job_id
        job_ids = []
        if results['metadatas'] and results['metadatas'][0]:
            for meta in results['metadatas'][0]:
                if meta.get('job_id') and meta['job_id'] not in job_ids:
                    job_ids.append(meta['job_id'])
        
        # 為了避免 API 等太久，我們取 Top 5 來做精準打分
        top_job_ids = job_ids[:5]
        
        if not top_job_ids:
            matching_status[user_id] = {"status": "done", "progress": 100, "log": "找不到任何相關職缺"}
            return

        matching_status[user_id] = {"status": "running", "progress": 30, "log": f"找到 {len(top_job_ids)} 筆潛在職缺，準備進行 AI 深度打分..."}
        
        for idx, j_id in enumerate(top_job_ids):
            cursor.execute("SELECT job_document FROM job_documents WHERE job_id = ?", (j_id,)) # 撈取完整職缺
            doc_row = cursor.fetchone()
            if not doc_row:
                continue
            
            job_doc = doc_row[0]
            
            # 呼叫 Gemini 進行打分
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
                response = call_gemini(prompt=prompt,temperature=0.1,output_json=True)
                
                # 清洗 JSON
                raw_text = response.text.strip()
                if raw_text.startswith('```json'): raw_text = raw_text[7:]
                elif raw_text.startswith('```'): raw_text = raw_text[3:]
                if raw_text.endswith('```'): raw_text = raw_text[:-3]
                
                score_data = json.loads(raw_text.strip())
                
                # 存入資料庫
                cursor.execute('''
                    INSERT OR REPLACE INTO user_matches (user_id, job_id, match_score, match_reasons, risk_reasons)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_id, j_id, score_data.get('match_score', 0), 
                      json.dumps(score_data.get('match_reasons', []), ensure_ascii=False),
                      json.dumps(score_data.get('risk_reasons', []), ensure_ascii=False)))
                conn.commit()
            except Exception as e:
                traceback.print_exc()
                print(f"Gemini 評分錯誤 {j_id}: {e}")
            
            # 更新進度
            current_prog = int(30 + ((idx + 1) / len(top_job_ids)) * 70)
            matching_status[user_id] = {"status": "running", "progress": current_prog, "log": f"AI 深度配對中... ({idx + 1}/{len(top_job_ids)})"}
        
        matching_status[user_id] = {"status": "done", "progress": 100, "log": "配對完成！"}
    except Exception as e:
        traceback.print_exc()
        matching_status[user_id] = {"status": "error", "progress": 0, "log": f"發生錯誤：{str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/api/trigger-match")
def trigger_match(background_tasks: BackgroundTasks, user_id: str = Form(...)):
    """觸發重新配對，丟到背景執行"""
    background_tasks.add_task(run_match_task, user_id)
    return {"status": "success", "message": "已開始背景配對"}

@app.get("/api/get-deep-analysis")
def get_deep_analysis(user_id: str, job_id: str):
    """取得職缺深度分析結果與職缺 Metadata"""
    try:
        # 1. 從 ChromaDB 撈取職缺 Metadata
        metadata = {}
        try:
            client = chromadb.PersistentClient(path="./my_job_db")
            collection = client.get_collection(name="job_chunks")
            results = collection.get(where={"job_id": job_id}, limit=1)
            if results and results.get('metadatas') and len(results['metadatas']) > 0:
                metadata = results['metadatas'][0]
        except Exception as e:
            print(f"ChromaDB 獲取 Metadata 失敗: {e}")

        # 若 ChromaDB 沒抓到，嘗試從 SQLite 補齊基礎資料
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        
        if not metadata or not metadata.get("jobName"):
            cursor.execute("SELECT job_name, cust_name, job_link FROM job_documents WHERE job_id = ?", (job_id,))
            doc_row = cursor.fetchone()
            if doc_row:
                metadata = {
                    "job_id": job_id,
                    "jobName": doc_row[0],
                    "custName": doc_row[1],
                    "analysisUrl": doc_row[2] or "",
                    "custUrl": "#",
                    "salaryType": "未填寫",
                    "address": "未提供",
                    "remoteWork": "無",
                    "hrBehaviorPR": 0.0,
                    "lastProcessedResumeAtTime": 0
                }
        print(f"【DEBUG】get_deep_analysis -> metadata: {metadata}")
        # 2. 從 SQLite 撈取使用者的分析紀錄
        cursor.execute('''
            SELECT match_tech_score, match_exp_score, perfect_matches, fatal_gaps, 
                   hidden_strengths, hr_red_flags, resume_tweaks, interview_prep, 
                   cover_letter, is_latest_resume, updated_at
            FROM job_deep_analysis
            WHERE user_id = ? AND job_id = ?
        ''', (user_id, job_id))
        row = cursor.fetchone()

        if row:
            analysis = {
                "match_tech_score": row[0] or 0,
                "match_exp_score": row[1] or 0,
                "perfect_matches": json.loads(row[2]) if row[2] else [],
                "fatal_gaps": json.loads(row[3]) if row[3] else [],
                "hidden_strengths": json.loads(row[4]) if row[4] else [],
                "hr_red_flags": json.loads(row[5]) if row[5] else [],
                "resume_tweaks": json.loads(row[6]) if row[6] else [],
                "interview_prep": json.loads(row[7]) if row[7] else [],
                "cover_letter": row[8],
                "is_latest_resume": row[9] if row[9] is not None else 1,
                "updated_at": row[10]
            }
            print(f"【DEBUG】get_deep_analysis -> row: {row}")
            print(f"【DEBUG】get_deep_analysis -> analysis: {analysis}")
            return {
                "status": "success",
                "metadata": metadata,
                "analysis": analysis
            }
        else:
            return {
                "status": "not_analyzed",
                "metadata": metadata
            }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"獲取深度分析失敗: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/api/run-deep-analysis")
def run_deep_analysis(user_id: str = Form(...), job_id: str = Form(...)):
    """執行職缺深度健檢與多維度匹配"""
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()

        # 1. 撈取履歷特徵
        cursor.execute("SELECT parsed_json FROM user_profiles WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return {"status": "error", "message": "找不到履歷資料，請先至 Profile 頁面上傳履歷！"}
        user_profile_json = user_row[0]

        # 2. 撈取職缺全文
        cursor.execute("SELECT job_document FROM job_documents WHERE job_id = ?", (job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            return {"status": "error", "message": "找不到該職缺的完整資料！"}
        job_document = job_row[0]

        # 3. 呼叫 Gemini 進行深度解析
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
        if raw_text.startswith('```json'): raw_text = raw_text[7:]
        elif raw_text.startswith('```'): raw_text = raw_text[3:]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]

        analysis_data = json.loads(raw_text.strip())

        # 4. 存入或更新 job_deep_analysis 資料表
        cursor.execute("""
            INSERT INTO job_deep_analysis (
                user_id, job_id, match_tech_score, match_exp_score,
                perfect_matches, fatal_gaps, hidden_strengths, hr_red_flags,
                resume_tweaks, is_latest_resume, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                match_tech_score = excluded.match_tech_score,
                match_exp_score = excluded.match_exp_score,
                perfect_matches = excluded.perfect_matches,
                fatal_gaps = excluded.fatal_gaps,
                hidden_strengths = excluded.hidden_strengths,
                hr_red_flags = excluded.hr_red_flags,
                resume_tweaks = excluded.resume_tweaks,
                is_latest_resume = 1,
                updated_at = CURRENT_TIMESTAMP
        """, (
            user_id, job_id,
            int(analysis_data.get('match_tech_score', 0)),
            int(analysis_data.get('match_exp_score', 0)),
            json.dumps(analysis_data.get('perfect_matches', []), ensure_ascii=False),
            json.dumps(analysis_data.get('fatal_gaps', []), ensure_ascii=False),
            json.dumps(analysis_data.get('hidden_strengths', []), ensure_ascii=False),
            json.dumps(analysis_data.get('hr_red_flags', []), ensure_ascii=False),
            json.dumps(analysis_data.get('resume_tweaks', []), ensure_ascii=False)
        ))
        conn.commit()

        # 撈出更新後的完整資料（包含可能既有的 interview_prep 與 cover_letter）
        cursor.execute('''
            SELECT interview_prep, cover_letter, updated_at
            FROM job_deep_analysis
            WHERE user_id = ? AND job_id = ?
        ''', (user_id, job_id))
        extra_row = cursor.fetchone()

        result_payload = {
            "match_tech_score": int(analysis_data.get('match_tech_score', 0)),
            "match_exp_score": int(analysis_data.get('match_exp_score', 0)),
            "perfect_matches": analysis_data.get('perfect_matches', []),
            "fatal_gaps": analysis_data.get('fatal_gaps', []),
            "hidden_strengths": analysis_data.get('hidden_strengths', []),
            "hr_red_flags": analysis_data.get('hr_red_flags', []),
            "resume_tweaks": analysis_data.get('resume_tweaks', []),
            "interview_prep": json.loads(extra_row[0]) if extra_row and extra_row[0] else [],
            "cover_letter": extra_row[1] if extra_row else None,
            "is_latest_resume": 1,
            "updated_at": extra_row[2] if extra_row else None
        }

        return {"status": "success", "data": result_payload}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"深度分析失敗: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/api/generate-cover-letter")
def generate_cover_letter(user_id: str = Form(...), job_id: str = Form(...)):
    """一鍵生成自我推薦信並存入資料庫"""
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        
        # 撈取使用者履歷特徵
        cursor.execute("SELECT parsed_json FROM user_profiles WHERE user_id = ?", (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return {"status": "error", "message": "找不到履歷資料，請先上傳履歷"}
        user_profile = user_row[0]
        
        # 撈取完整職缺資料
        cursor.execute("SELECT job_document FROM job_documents WHERE job_id = ?", (job_id,))
        job_row = cursor.fetchone()
        if not job_row:
            return {"status": "error", "message": "找不到該職缺的完整資料"}
        job_document = job_row[0]
        
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
        if raw_text.startswith('```json'): raw_text = raw_text[7:]
        elif raw_text.startswith('```'): raw_text = raw_text[3:]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]

        parsed_json = json.loads(raw_text.strip())
        letter_text = parsed_json.get("cover_letter", "生成推薦信失敗，請重試。")
        
        # 同步更新至 job_deep_analysis 資料表
        cursor.execute("""
            INSERT INTO job_deep_analysis (user_id, job_id, cover_letter, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                cover_letter = excluded.cover_letter,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, job_id, letter_text))
        conn.commit()

        return {"status": "success", "data": letter_text}
        
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        if 'conn' in locals(): conn.close()

@app.post("/api/generate-interview-questions")
def generate_interview_questions(user_id: str = Form(...), job_id: str = Form(...)):
    """針對致命缺口與 HR 潛在顧慮生成模擬面試題"""
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()

        # 撈取該次分析的致命缺口與 HR 顧慮
        cursor.execute("""
            SELECT fatal_gaps, hr_red_flags 
            FROM job_deep_analysis 
            WHERE user_id = ? AND job_id = ?
        """, (user_id, job_id))
        analysis_row = cursor.fetchone()

        fatal_gaps = "無特定技能缺口"
        hr_red_flags = "無特定風險顧慮"
        if analysis_row:
            if analysis_row[0]: fatal_gaps = analysis_row[0]
            if analysis_row[1]: hr_red_flags = analysis_row[1]

        # 撈取職缺原文以提供更真實的情境
        cursor.execute("SELECT job_document FROM job_documents WHERE job_id = ?", (job_id,))
        job_row = cursor.fetchone()
        job_document = job_row[0] if job_row else ""

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
        if raw_text.startswith('```json'): raw_text = raw_text[7:]
        elif raw_text.startswith('```'): raw_text = raw_text[3:]
        if raw_text.endswith('```'): raw_text = raw_text[:-3]

        interview_questions = json.loads(raw_text.strip())

        # 更新至 job_deep_analysis 資料庫
        cursor.execute("""
            INSERT INTO job_deep_analysis (user_id, job_id, interview_prep, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                interview_prep = excluded.interview_prep,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, job_id, json.dumps(interview_questions, ensure_ascii=False)))
        conn.commit()

        return {"status": "success", "data": interview_questions}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"生成面試題失敗: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/match-status")
def get_match_status(user_id: str):
    """前端輪詢用的狀態檢查 API"""
    status = matching_status.get(user_id, {"status": "idle", "progress": 0, "log": ""})
    return {"status": "success", "data": status}

@app.get("/api/get-matches")
def get_matches(user_id: str):
    """取得已算好的職缺卡片"""
    try:
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.job_id, m.match_score, m.match_reasons, m.risk_reasons, j.job_name, j.cust_name, j.job_link 
            FROM user_matches m
            JOIN job_documents j ON m.job_id = j.job_id
            WHERE m.user_id = ?
            ORDER BY m.match_score DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        
        matches = []
        for row in rows:
            matches.append({
                "job_id": row[0],
                "match_score": row[1],
                "match_reasons": json.loads(row[2]),
                "risk_reasons": json.loads(row[3]),
                "job_name": row[4],
                "cust_name": row[5],
                "job_link":row[6]
            })
        return {"status": "success", "data": matches}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if 'conn' in locals(): conn.close()

@app.get("/analysis")
def get_analysis_page(request: Request):
    # 這裡 context 設為 dashboard，這樣切過去時側邊欄的 dashboard 還是會發亮！
    return templates.TemplateResponse(
        request=request, 
        name="analysis.html", 
        context={"active_page": "dashboard"} 
    )

@app.get("/")
def get_home(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="home.html", 
        context={"active_page": "home"}
    )

@app.get("/dashboard")
def get_dashboard(request: Request):
    # 回傳給前端，並帶上 active_page="dashboard"
    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={"active_page": "dashboard"}
    )

@app.get("/scrapper")
def get_dashboard(request: Request):
    # 回傳給前端，並帶上 active_page="scrapper"
    return templates.TemplateResponse(
        request=request, 
        name="scrapper.html", 
        context={"active_page": "scrapper"}
    )

@app.get("/profile")
def get_profile_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="profile.html", 
        context={"active_page": "profile"}
    )
    
# 新增 AI 助理頁面的網頁路由
@app.get("/assistant")
def get_assistant(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="assistant.html", 
        context={"active_page": "assistant"}
    )
    
# 新增匹配頁面的網頁路由
@app.get("/matches")
def get_matches_page(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="matches.html", 
        context={"active_page": "matches"}
    )
app.mount("/static", StaticFiles(directory="static", html=True), name="static")