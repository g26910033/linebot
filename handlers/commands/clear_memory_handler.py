"""
清除對話歷史指令處理器
"""
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest)
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class ClearMemoryHandler:
    """處理清除對話歷史的指令。"""

    def __init__(self, storage_service: StorageService, configuration: Configuration):
        self.storage_service = storage_service
        self.configuration = configuration

    def handle(self, user_id: str, reply_token: str):
        """處理指令並回覆。"""
        self.storage_service.clear_chat_history(user_id)
        logger.info(f"Chat history cleared for user {user_id}")
        reply_text = "好的，我已經把我們之前的對話都忘光光了！"
        
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_text)]
            )
            line_bot_api.reply_message(reply_request)
