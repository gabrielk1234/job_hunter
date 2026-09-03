from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from schemas.scraper import ScraperStatusData, ScraperStatusResponse
from services.scraper_service import scraper_manager

router = APIRouter(tags=["Scraper"])


@router.websocket("/api/ws-scrape")
async def websocket_scrape(websocket: WebSocket) -> None:
    """處理爬蟲任務的雙向 WebSocket 即時通訊與進度廣播。"""
    await websocket.accept()
    scraper_manager.active_websockets.add(websocket)
    try:
        await websocket.send_json(
            {
                "type": "init_state",
                "is_running": scraper_manager.is_running,
                "progress": scraper_manager.progress,
                "logs": scraper_manager.logs,
                "latest_count": len(scraper_manager.latest_scraped_job_ids),
            }
        )

        while True:
            data = await websocket.receive_json()
            action = data.get("action", "start")
            if action == "start" or ("areas" in data and "jobcats" in data):
                areas = data.get("areas", [])
                jobcats = data.get("jobcats", [])
                keyword = data.get("keyword", "")
                started = scraper_manager.start_scrape(areas, jobcats, keyword)
                if not started:
                    await websocket.send_json(
                        {
                            "log": "⚠️ 爬蟲任務已在背景執行中，請稍候完成！",
                            "progress": scraper_manager.progress,
                            "is_running": True,
                            "latest_count": len(
                                scraper_manager.latest_scraped_job_ids
                            ),
                        }
                    )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        scraper_manager.active_websockets.discard(websocket)


@router.get("/api/scrape-status", response_model=ScraperStatusResponse)
def get_scrape_status() -> ScraperStatusResponse:
    """取得當前爬蟲任務的執行狀態與進度。"""
    data = ScraperStatusData(
        is_running=scraper_manager.is_running,
        progress=scraper_manager.progress,
        logs_count=len(scraper_manager.logs),
        latest_count=len(scraper_manager.latest_scraped_job_ids),
    )
    return ScraperStatusResponse(status="success", data=data)
