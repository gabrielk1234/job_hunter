from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi import Request
from pydantic import BaseModel
from tools.myown_tools import flatten
import asyncio
import sqlite3
import requests
import json
import chromadb
import traceback

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

@app.get("/api/sqlite-jobs")
def get_sqlite_jobs():
    """從 SQLite 撈取原始職缺 JSON 資料"""
    try:
        # 連線到你的 SQLite 資料庫 (檔名請確認跟爬蟲存的一樣)
        conn = sqlite3.connect('all_jobs.db')
        cursor = conn.cursor()
        
        # 撈取前 50 筆資料避免畫面卡頓
        cursor.execute("SELECT job_id, job_document, job_name, cust_name FROM job_documents LIMIT 50")
        rows = cursor.fetchall()
        
        jobs = []
        for row in rows:
            job_id, job_data_str, job_name, cust_name = row
            try:
                jobs.append({
                    "job_id": job_id,
                    "custName": cust_name,
                    "jobName": job_name,
                    "raw_json": flatten(job_data_str)
                })
            except Exception as e:
                print(f"解析 JSON 失敗 ID: {job_id}")
                
        return {"status": "success", "data": jobs}
    except Exception as e:
        return {"status": "error", "message": f"SQLite 連線錯誤: {str(e)}"}
    finally:
        if 'conn' in locals():
            conn.close()

@app.get("/api/chroma-jobs")
def get_chroma_jobs():
    """從 ChromaDB 撈取向量化後的 Metadata 與 Documents"""
    try:
        # 連線到本機的 ChromaDB 資料夾
        client = chromadb.PersistentClient(path="./my_job_db")
        collection = client.get_collection(name="job_chunks")
        
        # 撈取前 50 筆
        results = collection.get(limit=50)
        
        jobs = []
        if results and results.get('ids'):
            for i in range(len(results['ids'])):
                jobs.append({
                    "id": results['ids'][i],
                    "metadata": results['metadatas'][i] if results['metadatas'] else {},
                    "document": results['documents'][i] if results['documents'] else ""
                })
        return {"status": "success", "data": jobs}
    except Exception as e:
        return {"status": "error", "message": f"ChromaDB 連線錯誤: {str(e)}"}
    
@app.websocket("/api/ws-scrape")
async def websocket_scrape(websocket: WebSocket):
    # 接起前端打來的「電話」
    await websocket.accept()
    try:
        # 1. 接收前端傳來的 JSON 參數
        data = await websocket.receive_json()
        areas = data.get("areas", [])
        jobcats = data.get("jobcats", [])
        
        await websocket.send_json({"log": "🕸️ WebSocket 連線成功，背景爬蟲任務開始執行！", "progress": 2})
        
        # 讀取設定檔與連線資料庫
        config_file = './config.json'
        sqlite_db = 'all_jobs.db'
        table_name = 'job_documents'
        chroma_db = './my_job_db'
        chroma_collection = 'job_chunks'

        with open(config_file, 'r', encoding='utf-8') as f:
            config_json = json.load(f)
        cookies, headers = config_json['cookies'], config_json['headers']

        conn = sqlite3.connect(sqlite_db)
        cursor = conn.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                job_id TEXT PRIMARY KEY,
                job_document TEXT,
                job_name TEXT,
                cust_name TEXT
            )
        ''')
        conn.commit()

        client = chromadb.PersistentClient(path=chroma_db)
        collection = client.get_or_create_collection(name=chroma_collection)
        await websocket.send_json({"log": "✅ 資料庫連線完成", "progress": 5})

        area_str = ",".join(areas)
        jobcat_str = ",".join(jobcats)
        
        params = {
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
                cursor.execute(f'''
                    INSERT OR REPLACE INTO {table_name} (job_id, job_document,job_name,cust_name) 
                    VALUES (?, ?, ?, ?)
                ''', (id, documents,job_name,cust_name))
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
        # 1. 把最詳細的「案發現場 (哪行程式碼出錯)」印在後端的黑色終端機裡
        error_trace = traceback.format_exc()
        print(f"【系統異常】\n{error_trace}")
        
        # 2. 把錯誤的「類型」一起傳給前端 (例如會顯示 KeyError: 2)
        error_type = type(e).__name__
        await websocket.send_json({
            "log": f"❌ 致命錯誤 [{error_type}]: {str(e)}。詳細報錯請看後端終端機！", 
            "done": True
        })
        
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
    
# 新增 AI 助理頁面的網頁路由
@app.get("/assistant")
def get_assistant(request: Request):
    return templates.TemplateResponse(
        request=request, 
        name="assistant.html", 
        context={"active_page": "assistant"}
    )

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest):
    # 從 config 中抓取 API Key
    try:
        with open('./apikey.json','r',encoding='utf-8') as f:
            api_key_data = json.load(f)
    
        api_key = api_key_data.get('gemini_api_key', '')
        
        from tools.llm_agent import ask_gemini
    
        # 呼叫我們的獨立模組
        reply = ask_gemini(user_message=req.message, api_key=api_key)
        
        return {"status": "success", "reply": reply}
    except Exception as e:
        return {"status": "error", "reply": f"系統發生錯誤：{str(e)}"}

app.mount("/static", StaticFiles(directory="static", html=True), name="static")