"""
AI 繪圖指令處理器
"""
import threading
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ImageMessage, ReplyMessageRequest,
    PushMessageRequest)
from services.ai.image_service import AIImageService
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class DrawCommandHandler:
    """處理 '畫' 指令的類別。"""

    def __init__(
            self,
            image_service: AIImageService,
            storage_service: StorageService,
            configuration: Configuration):
        self.image_service = image_service
        self.storage_service = storage_service
        self.configuration = configuration

    def handle(self, user_id: str, reply_token: str, prompt: str) -> None:
        """處理繪圖指令。"""
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            if not prompt:
                reply_request = ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="請告訴我要畫什麼喔！\n格式：`畫 一隻可愛的貓`")]
                )
                line_bot_api.reply_message(reply_request)
                return

            initial_reply = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，正在為您繪製「{prompt}」，請稍候...")]
            )
            line_bot_api.reply_message(initial_reply)

        def task(user_id, prompt):
            try:
                translated_prompt = self.image_service.translate_prompt_for_drawing(prompt)
                image_bytes, status_msg = self.image_service.generate_image(translated_prompt)

                if image_bytes:
                    image_url, upload_status = self.storage_service.upload_image(image_bytes)
                    messages = [ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)] if image_url else [TextMessage(text=f"圖片上傳失敗: {upload_status}")]
                else:
                    messages = [TextMessage(text=f"繪圖失敗: {status_msg}")]
                
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    push_request = PushMessageRequest(to=user_id, messages=messages)
                    line_bot_api.push_message(push_request)

            except Exception as e:
                logger.error(f"Error in drawing task for user {user_id}: {e}", exc_info=True)
                try:
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        error_request = PushMessageRequest(to=user_id, messages=[TextMessage(text="繪圖時發生了未預期的錯誤。")])
                        line_bot_api.push_message(error_request)
                except Exception as api_e:
                    logger.error(f"Failed to send error message to user {user_id}: {api_e}", exc_info=True)

        threading.Thread(target=task, args=(user_id, prompt)).start()
