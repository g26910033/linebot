"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ImageMessage,
    QuickReply, QuickReplyItem, MessageAction as QuickReplyMessageAction,
    PushMessageRequest, ReplyMessageRequest)
from linebot.v3.webhooks import MessageEvent

from services.storage_service import StorageService
from .router import Router
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
    最終的文字訊息處理器。
    """

    def __init__(self, services: dict, configuration: Configuration):
        super().__init__(configuration, services['storage'])
        self.core_service = services['core']
        self.image_service = services['image']
        self.router = Router(services, configuration)

    def handle(self, event: MessageEvent):
        """處理文字訊息。"""
        user_id = event.source.user_id
        reply_token = event.reply_token
        user_message = event.message.text.strip()
        logger.info(
            f"TextMessageHandler received: '{user_message}' from {user_id}")

        if self.router.route(event):
            return

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
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    push_request = PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=ai_response)]
                    )
                    line_bot_api.push_message(push_request)
            except Exception as e:
                logger.error(f"Error in chat task for user {user_id}: {e}", exc_info=True)
                try:
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        error_request = PushMessageRequest(
                            to=user_id,
                            messages=[TextMessage(text="哎呀，處理您的訊息時發生了一點問題。")]
                        )
                        line_bot_api.push_message(error_request)
                except Exception as api_e:
                    logger.error(f"Failed to send error message to user {user_id}: {api_e}", exc_info=True)
        threading.Thread(target=task).start()

    def _handle_image_analysis(self, user_id: str, reply_token: str):
        """處理圖片分析指令。"""
        def task():
            try:
                last_image_id = self.storage_service.get_user_last_image_id(user_id)
                if not last_image_id:
                    reply_text = "請您先上傳一張圖片，我才能為您分析喔！"
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        push_request = PushMessageRequest(to=user_id, messages=[TextMessage(text=reply_text)])
                        line_bot_api.push_message(push_request)
                    return

                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    message_content = line_bot_api.get_message_content(message_id=last_image_id)
                    image_data = message_content
                    analysis_result = self.image_service.analyze_image(image_data)
                    push_request = PushMessageRequest(to=user_id, messages=[TextMessage(text=analysis_result)])
                    line_bot_api.push_message(push_request)
            except Exception as e:
                logger.error(f"Error during image analysis for user {user_id}: {e}", exc_info=True)
                try:
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        error_text = "抱歉，分析圖片時發生錯誤，請稍後再試。"
                        push_request = PushMessageRequest(to=user_id, messages=[TextMessage(text=error_text)])
                        line_bot_api.push_message(push_request)
                except Exception as api_e:
                    logger.error(f"Failed to send error message to user {user_id}: {api_e}", exc_info=True)
        threading.Thread(target=task).start()

    def _handle_image_to_image_init(self, user_id: str, reply_token: str):
        """處理以圖生圖的初始指令。"""
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            last_image_id = self.storage_service.get_user_last_image_id(user_id)
            if not last_image_id:
                reply_text = "請您先上傳一張要做為基底的圖片喔！"
                reply_request = ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply_text)])
                line_bot_api.reply_message(reply_request)
                return

            self.storage_service.set_user_state(user_id, "waiting_image_prompt")
            reply_text = "收到！請現在用文字告訴我，您想如何修改這張圖片？（例如：`讓它變成梵谷的風格`）"
            reply_request = ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply_text)])
            line_bot_api.reply_message(reply_request)

    def _handle_image_to_image_prompt(self, user_id: str, prompt: str, reply_token: str):
        """處理使用者輸入的以圖生圖提示詞。"""
        self.storage_service.set_user_state(user_id, "")
        cleaned_prompt = prompt.strip().strip('`')
        last_image_id = self.storage_service.get_user_last_image_id(user_id)

        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            if not last_image_id:
                reply_text = "抱歉，我找不到您上次傳送的圖片，請重新上傳一次。"
                reply_request = ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply_text)])
                line_bot_api.reply_message(reply_request)
                return

            initial_reply = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，正在為您使用「{cleaned_prompt}」的風格修改圖片，請稍候...")])
            line_bot_api.reply_message(initial_reply)

        def task():
            try:
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    base_image_bytes = line_bot_api.get_message_content(message_id=last_image_id)
                    image_bytes, status_msg = self.image_service.generate_image_from_image(base_image_bytes, cleaned_prompt)

                    if image_bytes:
                        image_url, upload_status = self.storage_service.upload_image(image_bytes)
                        messages = [ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)] if image_url else [TextMessage(text=f"圖片上傳失敗: {upload_status}")]
                    else:
                        messages = [TextMessage(text=f"以圖生圖失敗: {status_msg}")]
                    
                    push_request = PushMessageRequest(to=user_id, messages=messages)
                    line_bot_api.push_message(push_request)
            except Exception as e:
                logger.error(f"Error in image-to-image task for user {user_id}: {e}", exc_info=True)
                try:
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        error_text = "抱歉，以圖生圖時發生未預期的錯誤。"
                        push_request = PushMessageRequest(to=user_id, messages=[TextMessage(text=error_text)])
                        line_bot_api.push_message(push_request)
                except Exception as api_e:
                    logger.error(f"Failed to send error message to user {user_id}: {api_e}", exc_info=True)
        threading.Thread(target=task).start()


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
    def handle(self, event: MessageEvent):
        user_id = event.source.user_id
        reply_token = event.reply_token
        latitude = event.message.latitude
        longitude = event.message.longitude
        logger.info(f"Received location from {user_id}: lat={latitude}, lon={longitude}")
        self.storage_service.set_user_last_location(user_id, latitude, longitude)

        reply_text = "收到您的位置了！現在您可以問我「附近有什麼好吃的？」或「幫我找最近的咖啡廳」囉！"
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_request = ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=reply_text)])
            line_bot_api.reply_message(reply_request)
