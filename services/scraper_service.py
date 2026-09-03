import asyncio
import json
import random as rd
import traceback
from typing import Any, Dict, List, Optional, Set
import browser_cookie3
from curl_cffi import requests as cffi_requests
from fastapi import WebSocket
import requests

from repositories.job_repository import JobRepository
from tools.pharse import create_chunks, get_document, get_metadata


class ScraperManager:
    """負責管理 104 職缺爬蟲的背景執行、即時 WebSocket 廣播與資料持久化。"""

    def __init__(self) -> None:
        self.is_running: bool = False
        self.progress: int = 0
        self.logs: List[Dict[str, Any]] = []
        self.latest_scraped_job_ids: List[str] = []
        self.active_websockets: Set[WebSocket] = set()
        self.task: Optional[asyncio.Task] = None

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """向所有已連線的前端 WebSocket 客戶端廣播訊息。"""
        self.logs.append(message)
        if len(self.logs) > 1000:
            self.logs.pop(0)

        if "progress" in message:
            self.progress = message["progress"]

        dead_ws: List[WebSocket] = []
        for ws in list(self.active_websockets):
            try:
                await ws.send_json(message)
            except Exception:
                dead_ws.append(ws)

        for ws in dead_ws:
            self.active_websockets.discard(ws)

    def start_scrape(self, areas: List[str], jobcats: List[str], keyword: str) -> bool:
        """啟動非同步背景爬蟲任務。"""
        if self.is_running:
            return False
        self.is_running = True
        self.progress = 0
        self.logs = []
        self.latest_scraped_job_ids = []
        self.task = asyncio.create_task(self._run_scrape(areas, jobcats, keyword))
        return True

    async def _run_scrape(
        self, areas: List[str], jobcats: List[str], keyword: str
    ) -> None:
        """執行 104 API 職缺清單與詳細頁面爬取流程。"""
        try:
            await self.broadcast({"log": "🕸️ 背景爬蟲任務開始執行！", "progress": 2})

            config_file = "./config.json"
            with open(config_file, "r", encoding="utf-8") as f:
                config_json = json.load(f)
            headers = config_json["headers"]

            cookies = browser_cookie3.chrome(
                domain_name="104.com.tw",
                cookie_file=r"/Users/gkko/Library/Application Support/Google/Chrome/Profile 13/Cookies",
            )

            await self.broadcast({"log": "✅ 資料庫連線完成", "progress": 5})

            area_str = ",".join(areas)
            jobcat_str = ",".join(jobcats)
            await self.broadcast(
                {"log": f"設定條件為: 關鍵字: {keyword}", "progress": 8}
            )

            params = {
                "area": area_str,
                "jobcat": jobcat_str,
                "jobsource": "joblist_search",
                "mode": "s",
                "orLabel": "foreigners@overseasStudents^20,foreigners@chineseDiasporas^20",
                "order": "16",
                "page": "1",
                "pagesize": "20",
            }
            if keyword:
                params["keyword"] = keyword

            await self.broadcast(
                {"log": "🔍 正在向 104 請求職缺列表...", "progress": 10}
            )

            response = await asyncio.to_thread(
                cffi_requests.get,
                "https://www.104.com.tw/jobs/search/api/jobs",
                params=params,
                cookies=cookies,
                headers=headers,
                impersonate="chrome120",
            )

            if response.status_code != 200:
                await self.broadcast(
                    {
                        "log": "❌ 無法獲取列表，可能是 Cookie 過期或是被擋了",
                        "done": True,
                    }
                )
                return

            job_json = response.json().get("data", [])
            total_jobs = len(job_json)

            if total_jobs == 0:
                await self.broadcast(
                    {"log": "⚠️ 找不到符合條件的職缺喔！", "progress": 100, "done": True}
                )
                return

            await self.broadcast(
                {
                    "log": f"📊 共找到 {total_jobs} 個職缺，準備開始抓取細節！",
                    "progress": 15,
                }
            )

            for idx, job in enumerate(job_json, 1):
                job_id = job["jobNo"]
                job_code = job["link"]["job"].split("/")[-1]
                cust_name = job.get("custName", "未知公司")

                await self.broadcast(
                    {"log": f"➤ [{idx}/{total_jobs}] 正在抓取：{cust_name} - {job_code}..."}
                )

                job_detail_response = await asyncio.to_thread(
                    requests.get,
                    f"https://www.104.com.tw/api/jobs/{job_code}",
                    cookies=cookies,
                    headers=headers,
                )

                if job_detail_response.status_code == 200:
                    job_detail_json = job_detail_response.json().get("data")

                    # 解析並寫入 ChromaDB
                    documents = get_document(job_detail_json)
                    metadata = get_metadata(job_detail_json)
                    chunks = create_chunks(
                        job_id=job_id,
                        full_document=documents,
                        base_metadata=metadata,
                    )

                    chunk_ids = [str(c["ids"]) for c in chunks]
                    chunk_documents = [c["text"] for c in chunks]
                    chunk_metadatas = [c["metadata"] for c in chunks]

                    JobRepository.add_chroma_chunks(
                        documents=chunk_documents,
                        metadatas=chunk_metadatas,
                        ids=chunk_ids,
                    )

                    # 寫入 SQLite
                    job_name = metadata["jobName"]
                    cust_name = metadata["custName"]
                    job_link = metadata["analysisUrl"].replace(
                        "s/apply/analysis/", "/"
                    )

                    JobRepository.upsert_job(
                        job_id=job_id,
                        job_document=documents,
                        job_name=job_name,
                        cust_name=cust_name,
                        job_link=job_link,
                    )

                    if job_id not in self.latest_scraped_job_ids:
                        self.latest_scraped_job_ids.append(job_id)

                    progress_percent = int(15 + (idx / total_jobs) * 85)
                    await self.broadcast(
                        {
                            "log": f"  └─ ✅ 成功存入：{job_id}",
                            "progress": progress_percent,
                            "latest_count": len(self.latest_scraped_job_ids),
                        }
                    )
                else:
                    await self.broadcast(
                        {"log": f"  └─ ❌ {job_code} 獲取資料失敗！"}
                    )

                sleep_time = rd.randint(2, 5)
                await self.broadcast(
                    {"log": f"  └─ ⏳ 休息 {sleep_time} 秒以防被封鎖..."}
                )
                await asyncio.sleep(sleep_time)

            await self.broadcast(
                {
                    "log": f"🎉 爬蟲任務全部完工！共抓取 {len(self.latest_scraped_job_ids)} 筆職缺。",
                    "progress": 100,
                    "done": True,
                    "latest_count": len(self.latest_scraped_job_ids),
                }
            )

        except Exception as e:
            error_type = type(e).__name__
            await self.broadcast(
                {
                    "log": f"❌ 致命錯誤 [{error_type}]: {str(e)}。詳細報錯請看後端終端機！",
                    "done": True,
                }
            )
        finally:
            self.is_running = False


scraper_manager = ScraperManager()
