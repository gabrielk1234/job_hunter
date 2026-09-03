from typing import Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    """AI 聊天請求格式。"""
    message: str


class ChatResponse(BaseModel):
    """AI 聊天回應格式。"""
    status: str
    reply: str
