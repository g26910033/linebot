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
    提供共用錯誤回覆與地點輪播訊息產生。
    """
    def __init__(self, ai_service: AIService, storage_service: StorageService) -> None:
        self.ai_service: AIService = ai_service
        self.storage_service: StorageService = storage_service

    # ... (後續的 class 內容與您上傳的版本相同，此處省略以保持簡潔)