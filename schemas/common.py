from typing import Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """基礎標準 API 回傳格式。"""
    status: str
    message: Optional[str] = None
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    """錯誤回傳格式。"""
    status: str = "error"
    message: str
