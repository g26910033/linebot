"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading

from linebot.v3.messaging import (
    MessagingApi, TextMessage, QuickReply, QuickReplyItem,
    MessageAction as QuickReplyMessageAction, PushMessageRequest,
    ReplyMessageRequest)
from linebot.v3.webhooks import MessageEvent

from services.storage_service import StorageService
from .router import Router
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseMessageHandler:
    """所有處理器的基類，提供共用方法。"""

    def __init__(self, line_bot_api: MessagingApi,
                 storage_service: StorageService):
        self.line_bot_api = line_bot_api
        self.storage_service = storage_service


class TextMessageHandler(BaseMessageHandler):
    """
    最終的文字訊息處理器。
    只處理無法被路由器路由的訊息，通常是通用的 AI 對話。
    """

    def __init__(self, services: dict, line_bot_api: MessagingApi):
        super().__init__(line_bot_api, services['storage'])
        self.core_service = services['core']
        self.image_service = services['image']
        self.router = Router(services, line_bot_api)

    def handle(self, event: MessageEvent):
        """處理文字訊息。"""
        user_id = event.source.user_id
        reply_token = event.reply_token
        user_message = event.message.text.strip()
        logger.info(
            f"TextMessageHandler received: '{user_message}' from {user_id}")

        # 1. 嘗試路由到特定指令處理器
        if self.router.route(event):
            return

        # 2. 處理圖片相關的特殊指令
        if user_message == "[指令]圖片分析":
            self._handle_image_analysis(user_id, reply_token)
            return
        if user_message == "[指令]以圖生圖":
            self._handle_image_to_image_init(user_id, reply_token)
            return

        user_state = self.storage_service.get_user_state(user_id)
        if user_state == "waiting_image_prompt":
            self._handle_image_to_image_prompt(
                user_id, user_message, reply_token)
            return

        # 3. 如果都無法路由，則視為一般對話
        self._handle_chat(user_id, user_message)

    def _handle_chat(self, user_id: str, user_message: str):
        """處理一般對話。"""
        def task():
            try:
                history = self.storage_service.get_chat_history(user_id)
                ai_response, updated_history = self.core_service.chat_with_history(
                    user_message, history)
                self.storage_service.save_chat_history(
                    user_id, updated_history)
                push_message_request = PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=ai_response)]
                )
                self.line_bot_api.push_message(push_message_request)
            except Exception as e:
                logger.error(
                    f"Error in chat task for user {user_id}: {e}",
                    exc_info=True)
                error_message_request = PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text="哎呀，處理您的訊息時發生了一點問題。")]
                )
                self.line_bot_api.push_message(error_message_request)
        threading.Thread(target=task).start()

    def _handle_image_analysis(self, user_id: str, reply_token: str):
        # ... (這部分邏輯也應該遷移，但暫時保留以求功能完整)
        pass

    def _handle_image_to_image_init(self, user_id: str, reply_token: str):
        # ... (同上)
        pass

    def _handle_image_to_image_prompt(
            self, user_id: str, prompt: str, reply_token: str):
        # ... (同上)
        pass


class ImageMessageHandler(BaseMessageHandler):
    """圖片訊息處理器"""

    def handle(self, event: MessageEvent):
        user_id = event.source.user_id
        reply_token = event.reply_token
        message_id = event.message.id
        logger.info(
            f"Received image from {user_id}, message_id: {message_id}")

        self.storage_service.set_user_last_image_id(user_id, message_id)

        quick_reply = QuickReply(items=[
            QuickReplyItem(action=QuickReplyMessageAction(
                label="🔍 圖片分析", text="[指令]圖片分析")),
            QuickReplyItem(action=QuickReplyMessageAction(
                label="🎨 以圖生圖", text="[指令]以圖生圖")),
        ])
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[
                TextMessage(
                    text="收到您的圖片了！請問您想做什麼？",
                    quick_reply=quick_reply)
            ]
        )
        self.line_bot_api.reply_message(reply_request)


class LocationMessageHandler(BaseMessageHandler):
    """位置訊息處理器"""

    def __init__(self, line_bot_api: MessagingApi,
                 storage_service: StorageService):
        super().__init__(line_bot_api, storage_service)

    def handle(self, event: MessageEvent):
        # ... (地點處理邏輯也應遷移到 router/handler)
        pass
