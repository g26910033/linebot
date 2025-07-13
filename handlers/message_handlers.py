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
        try:
            api_response = line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
            )
            # 記錄非 200 的狀態碼，以便追蹤 API 錯誤
            if api_response.status_code != 200:
                logger.error(f"Error sending reply message. Status: {api_response.status_code}, Body: {api_response.data}")
        except Exception as e:
            logger.error(f"Exception when sending reply message: {e}", exc_info=True)

    def _create_location_carousel(self, places_list, line_bot_api, user_id):
        # ... (此函式維持不變)
        pass

class TextMessageHandler(MessageHandler):
    """文字訊息處理器"""

    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        """
        處理所有文字訊息的統一入口。
        根據訊息內容分派到不同的處理函式。
        """
        user_id = event.source.user_id
        reply_token = event.reply_token
        user_message = event.message.text.strip()
        logger.info(f"Received text message from user {user_id}: '{user_message}'")

        try:
            if self._is_draw_command(user_message):
                logger.debug(f"User {user_id} triggered draw command.")
                prompt = user_message.replace("畫", "", 1).strip()
                self._handle_draw_command(prompt, user_id, reply_token, line_bot_api)
            elif self._is_clear_history_command(user_message):
                logger.debug(f"User {user_id} triggered clear history command.")
                self._handle_clear_history(user_id, reply_token, line_bot_api)
            elif self._is_search_command(user_message):
                logger.debug(f"User {user_id} triggered search command.")
                self._handle_search_command(user_message, user_id, reply_token, line_bot_api)
            else:
                # 【核心修正】確保所有其他訊息都進入一般對話流程
                logger.debug(f"User {user_id} triggered general chat.")
                self._handle_chat(user_message, user_id, reply_token, line_bot_api)
        except Exception as e:
            logger.error(f"Error handling text message for user {user_id}: {e}", exc_info=True)
            self._reply_error(line_bot_api, reply_token, "處理您的訊息時發生了未預期的錯誤，請稍後再試。")

    def _is_draw_command(self, text: str) -> bool:
        return text.startswith("畫")

    def _is_clear_history_command(self, text: str) -> bool:
        return text in ["清除對話", "忘記對話", "清除記憶"]

    def _is_search_command(self, text: str) -> bool:
        return text.startswith("搜尋") or text.startswith("尋找")

    def _handle_chat(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        def task():
            """在背景執行緒中處理耗時的 AI 對話任務"""
            try:
                history = self.storage_service.get_chat_history(user_id)
                ai_response, updated_history = self.ai_service.chat_with_history(user_message, history)
                self.storage_service.save_chat_history(user_id, updated_history)
                line_bot_api.push_message(
                    PushMessageRequest(to=user_id, messages=[TextMessage(text=ai_response)])
                )
            except Exception as e:
                logger.error(f"Error in chat background task for user {user_id}: {e}", exc_info=True)
                try:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，處理您的訊息時發生了一點問題，請稍後再試一次。")]))
                except Exception as push_e:
                    logger.error(f"Failed to push error message to user {user_id}: {push_e}", exc_info=True)

        # 立即回覆使用者，避免 reply_token 過期
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="好的，請稍候...")])
        )
        threading.Thread(target=task).start()

    def _handle_draw_command(self, prompt: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not prompt:
            self._reply_error(line_bot_api, reply_token, "請告訴我要畫什麼喔！\n格式：`畫 一隻可愛的貓`")
            return

        def task():
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"好的，正在為您繪製「{prompt}」，請稍候...")]))
            translated_prompt = self.ai_service.translate_prompt_for_drawing(prompt)
            image_bytes, status_msg = self.ai_service.generate_image(translated_prompt)
            if image_bytes:
                image_url, upload_status = self.storage_service.upload_image_to_cloudinary(image_bytes)
                if image_url:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)]))
                else:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"圖片上傳失敗: {upload_status}")]))
            else:
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"繪圖失敗: {status_msg}")]))

        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到繪圖指令！")]))
        threading.Thread(target=task).start()

    def _handle_clear_history(self, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        self.storage_service.clear_chat_history(user_id)
        self._reply_error(line_bot_api, reply_token, "好的，我們的對話記憶已經清除！")

    def _handle_search_command(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if "附近" in user_message:
            keyword = user_message.replace("尋找", "").replace("附近", "").strip()
            self.storage_service.set_nearby_query(user_id, keyword)
            self._reply_error(line_bot_api, reply_token, f"好的，請分享您的位置，我將為您尋找附近的「{keyword}」。")
        else:
            query = user_message.replace("搜尋", "").strip()
            places = self.ai_service.search_location(query)
            if places and places.get("places"):
                carousel = self._create_location_carousel(places["places"], line_bot_api, user_id)
                line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[carousel]))
            else:
                self._reply_error(line_bot_api, reply_token, f"抱歉，找不到關於「{query}」的地點資訊。")

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