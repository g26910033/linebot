"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading

from linebot.v3.messaging.api.messaging_api import MessagingApi
from linebot.v3.messaging.models.text_message import TextMessage
from linebot.v3.messaging.models.image_message import ImageMessage
from linebot.v3.messaging.models.quick_reply import QuickReply
from linebot.v3.messaging.models.quick_reply_item import QuickReplyItem
from linebot.v3.messaging.models.message_action import MessageAction as QuickReplyMessageAction
from linebot.v3.messaging.models.push_message_request import PushMessageRequest
from linebot.v3.messaging.models.reply_message_request import ReplyMessageRequest
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
        """處理圖片分析指令。"""
        def task():
            last_image_id = self.storage_service.get_user_last_image_id(user_id)
            if not last_image_id:
                reply_text = "請您先上傳一張圖片，我才能為您分析喔！"
                push_request = PushMessageRequest(
                    to=user_id, messages=[TextMessage(text=reply_text)])
                self.line_bot_api.push_message(push_request)
                return

            try:
                # 在新版 SDK 中，直接從主 API 物件下載內容
                message_content = self.line_bot_api.get_message_content(
                    message_id=last_image_id)
                image_data = message_content
                analysis_result = self.image_service.analyze_image(image_data)
                push_request = PushMessageRequest(
                    to=user_id, messages=[TextMessage(text=analysis_result)])
                self.line_bot_api.push_message(push_request)
            except Exception as e:
                logger.error(
                    f"Error during image analysis for user {user_id}: {e}",
                    exc_info=True)
                error_text = "抱歉，分析圖片時發生錯誤，請稍後再試。"
                push_request = PushMessageRequest(
                    to=user_id, messages=[TextMessage(text=error_text)])
                self.line_bot_api.push_message(push_request)

        threading.Thread(target=task).start()

    def _handle_image_to_image_init(self, user_id: str, reply_token: str):
        """處理以圖生圖的初始指令。"""
        last_image_id = self.storage_service.get_user_last_image_id(user_id)
        if not last_image_id:
            reply_text = "請您先上傳一張要做為基底的圖片喔！"
            reply_request = ReplyMessageRequest(
                reply_token=reply_token, messages=[TextMessage(text=reply_text)])
            self.line_bot_api.reply_message(reply_request)
            return

        self.storage_service.set_user_state(user_id, "waiting_image_prompt")
        reply_text = "收到！請現在用文字告訴我，您想如何修改這張圖片？（例如：`讓它變成梵谷的風格`）"
        reply_request = ReplyMessageRequest(
            reply_token=reply_token, messages=[TextMessage(text=reply_text)])
        self.line_bot_api.reply_message(reply_request)

    def _handle_image_to_image_prompt(
            self, user_id: str, prompt: str, reply_token: str):
        """處理使用者輸入的以圖生圖提示詞。"""
        self.storage_service.set_user_state(user_id, "") # 清除狀態
        cleaned_prompt = prompt.strip().strip('`') # 清除頭尾的 ` 符號
        last_image_id = self.storage_service.get_user_last_image_id(user_id)

        if not last_image_id:
            reply_text = "抱歉，我找不到您上次傳送的圖片，請重新上傳一次。"
            reply_request = ReplyMessageRequest(
                reply_token=reply_token, messages=[TextMessage(text=reply_text)])
            self.line_bot_api.reply_message(reply_request)
            return

        # 異步處理圖片生成
        def task():
            try:
                # 下載基底圖片
                base_image_bytes = self.line_bot_api.get_message_content(message_id=last_image_id)

                # 生成新圖片
                image_bytes, status_msg = self.image_service.generate_image_from_image(
                    base_image_bytes, cleaned_prompt)

                if image_bytes:
                    image_url, upload_status = self.storage_service.upload_image(image_bytes)
                    if image_url:
                        messages = [ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)]
                    else:
                        messages = [TextMessage(text=f"圖片上傳失敗: {upload_status}")]
                else:
                    messages = [TextMessage(text=f"以圖生圖失敗: {status_msg}")]

                push_request = PushMessageRequest(to=user_id, messages=messages)
                self.line_bot_api.push_message(push_request)

            except Exception as e:
                logger.error(f"Error in image-to-image task for user {user_id}: {e}", exc_info=True)
                error_text = "抱歉，以圖生圖時發生未預期的錯誤。"
                push_request = PushMessageRequest(to=user_id, messages=[TextMessage(text=error_text)])
                self.line_bot_api.push_message(push_request)

        # 先給予一個快速的回覆，避免 token 過期
        initial_reply = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=f"好的，正在為您使用「{cleaned_prompt}」的風格修改圖片，請稍候...")])
        self.line_bot_api.reply_message(initial_reply)

        threading.Thread(target=task).start()


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
        """處理位置訊息，儲存經緯度並回覆。"""
        user_id = event.source.user_id
        reply_token = event.reply_token
        latitude = event.message.latitude
        longitude = event.message.longitude

        logger.info(
            f"Received location from {user_id}: "
            f"lat={latitude}, lon={longitude}")

        # 儲存使用者最後分享的位置
        self.storage_service.set_user_last_location(
            user_id, latitude, longitude)

        # 回覆確認訊息
        reply_text = (
            "收到您的位置了！現在您可以問我「附近有什麼好吃的？」"
            "或「幫我找最近的咖啡廳」囉！"
        )
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=reply_text)]
        )
        self.line_bot_api.reply_message(reply_request)
