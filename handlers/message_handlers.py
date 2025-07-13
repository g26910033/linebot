"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
from urllib.parse import quote_plus
from linebot.v3.messaging import (
    MessagingApi, MessagingApiBlob,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage, TemplateMessage,
    CarouselTemplate, CarouselColumn, URIAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent
from services.ai_service import AIService
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)

class MessageHandler:
    """訊息處理器基類。"""
    def __init__(self, ai_service: AIService, storage_service: StorageService) -> None:
        self.ai_service = ai_service
        self.storage_service = storage_service

    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
        )

    def _create_location_carousel(self, places_list, line_bot_api, user_id):
        # ... (此函式維持不變)
        pass

class TextMessageHandler(MessageHandler):
    """文字訊息處理器"""
    
    # 【核心修正】新增 handle 方法作為統一入口
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_message = event.message.text.strip()
        # ... (後續的 if/elif 判斷邏輯與您現有的程式碼完全相同)
    
    # ... (所有 _is_... 和 _handle_... 的輔助函式維持不變)

class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""

    # 【核心修正】新增 handle 方法作為統一入口
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        # ... (後續的 try/except 邏輯與您現有的程式碼完全相同)
        pass

class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""

    # 【核心修正】新增 handle 方法作為統一入口
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        # ... (後續的 try/except 邏輯與您現有的程式碼完全相同)
        pass