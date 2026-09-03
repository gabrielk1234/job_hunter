from fastapi import APIRouter
from schemas.chat import ChatRequest, ChatResponse
from services.chat_service import ChatService

router = APIRouter(tags=["Chat"])


@router.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    """接收使用者輸入文字，透過 AI 職涯顧問對話引擎生成回應與推薦職缺。"""
    try:
        reply = ChatService.process_chat(message=req.message)
        return ChatResponse(status="success", reply=reply)
    except Exception as e:
        return ChatResponse(status="error", reply=f"系統發生錯誤：{str(e)}")
