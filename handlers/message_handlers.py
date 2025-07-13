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
    """
    訊息處理器基類。
    """
    def __init__(self, ai_service: AIService, storage_service: StorageService) -> None:
        self.ai_service = ai_service
        self.storage_service = storage_service

    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        """回覆錯誤訊息。"""
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
        )
    
    # ... (此處省略 _create_location_carousel 函式，因為它在您的檔案中已存在且正確)

class TextMessageHandler(MessageHandler):
    """文字訊息處理器"""
    # ... (此處省略整個 TextMessageHandler 類別，因為它在您的檔案中已存在且正確)

class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""
    # ... (此處省略整個 ImageMessageHandler 類別，因為它在您的檔案中已存在且正確)

class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""
    # ... (此處省略整個 LocationMessageHandler 類別，因為它在您的檔案中已存在且正確)