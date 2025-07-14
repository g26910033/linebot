"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ImageMessage,
    QuickReply, QuickReplyItem, MessageAction as QuickReplyMessageAction,
    PushMessageRequest, ReplyMessageRequest)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from services.storage_service import StorageService
from .central_handler import CentralHandler
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseMessageHandler:
    """所有處理器的基類，提供共用方法。"""

    def __init__(self, configuration: Configuration,
                 storage_service: StorageService):
        self.configuration = configuration
        self.storage_service = storage_service


class TextMessageHandler(BaseMessageHandler):
    """
    文字訊息處理器，現在作為中央處理器的入口。
    """

    def __init__(self, services: dict, configuration: Configuration):
        super().__init__(configuration, services['storage'])
        self.central_handler = CentralHandler(services, configuration)

    def handle(self, event: MessageEvent):
        """處理文字訊息，直接交給中央處理器。"""
        self.central_handler.handle(event)
    
    def handle_postback(self, event):
        # 暫時將 postback 也交給 central_handler
        # 未來可以考慮為 postback 建立專門的處理邏輯
        logger.info(f"Passing postback event to CentralHandler")
        self.central_handler.handle_postback(event)


class ImageMessageHandler(BaseMessageHandler):
    """圖片訊息處理器"""
    def handle(self, event: MessageEvent):
        user_id = event.source.user_id
        reply_token = event.reply_token
        message_id = event.message.id
        logger.info(f"Received image from {user_id}, message_id: {message_id}")
        self.storage_service.set_user_last_image_id(user_id, message_id)

        quick_reply = QuickReply(items=[
            QuickReplyItem(action=QuickReplyMessageAction(label="🔍 圖片分析", text="[指令]圖片分析")),
            QuickReplyItem(action=QuickReplyMessageAction(label="🎨 以圖生圖", text="[指令]以圖生圖")),
        ])
        
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="收到您的圖片了！請問您想做什麼？", quick_reply=quick_reply)]
            )
            line_bot_api.reply_message(reply_request)


class LocationMessageHandler(BaseMessageHandler):
    """位置訊息處理器"""
    def __init__(self, configuration: Configuration, storage_service: StorageService, text_handler: TextMessageHandler):
        super().__init__(configuration, storage_service)
        self.text_handler = text_handler

    def handle(self, event: MessageEvent):
        user_id = event.source.user_id
        reply_token = event.reply_token
        latitude = event.message.latitude
        longitude = event.message.longitude
        logger.info(f"Received location from {user_id}: lat={latitude}, lon={longitude}")
        self.storage_service.set_user_last_location(user_id, latitude, longitude)

        pending_query = self.storage_service.get_nearby_query(user_id)
        if pending_query:
            self.storage_service.delete_nearby_query(user_id)
            fake_text = f"尋找附近{pending_query}"
            # 建立一個假的文字訊息事件，並重新交給 TextMessageHandler 處理
            fake_event = MessageEvent(
                source=event.source,
                reply_token=event.reply_token,
                message=TextMessage(text=fake_text),
                timestamp=event.timestamp,
                mode=event.mode
            )
            self.text_handler.handle(fake_event)
        else:
            reply_text = "收到您的位置了！現在您可以問我「附近有什麼好吃的？」或「幫我找最近的咖啡廳」囉！"
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                reply_request = ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply_text)])
                line_bot_api.reply_message(reply_request)
