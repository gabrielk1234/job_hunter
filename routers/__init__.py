from routers.analysis import router as analysis_router
from routers.chat import router as chat_router
from routers.jobs import router as jobs_router
from routers.matching import router as matching_router
from routers.profile import router as profile_router
from routers.scraper import router as scraper_router
from routers.views import router as views_router

__all__ = [
    "analysis_router",
    "chat_router",
    "jobs_router",
    "matching_router",
    "profile_router",
    "scraper_router",
    "views_router",
]
