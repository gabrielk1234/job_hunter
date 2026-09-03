from tools.llm_agent import ask_gemini


class ChatService:
    """處理 AI 聊天商業邏輯。"""

    @staticmethod
    def process_chat(message: str, user_id: str = "default_user") -> str:
        """接收使用者訊息並透過 Gemini 職涯顧問對話引擎獲取回應。"""
        return ask_gemini(user_message=message, user_id=user_id)
