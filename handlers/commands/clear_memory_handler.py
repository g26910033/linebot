"""
清除對話歷史指令處理器
"""
from linebot.v3.messaging import (
    MessagingApi, TextMessage, ReplyMessageRequest)
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class ClearMemoryHandler:
    """處理清除對話歷史的指令。"""

    def __init__(self, storage_service: StorageService, line_bot_api: MessagingApi):
        self.storage_service = storage_service
        self.line_bot_api = line_bot_api

    def handle(self, user_id: str, reply_token: str):
        """處理指令並回覆。"""
        self.storage_service.clear_chat_history(user_id)
        logger.info(f"Chat history cleared for user {user_id}")
        reply_text = "好的，我已經把我們之前的對話都忘光光了！"
        
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
        self.line_bot_api.reply_message(reply_request)
