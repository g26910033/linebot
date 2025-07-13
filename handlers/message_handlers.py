"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
import re
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

    def _create_location_carousel(self, places_list: list) -> TemplateMessage | TextMessage:
        """根據地點列表建立輪播訊息"""
        columns = []
        # 限制輪播項目數量，最多10個
        for place in places_list[:10]:
            try:
                title = place.get('displayName', {}).get('text', '地點資訊')
                # 確保標題長度不超過40個字元
                title = title[:40]

                address = place.get('formattedAddress', '地址未提供')
                # 確保地址長度不超過60個字元
                address = address[:60]

                # 建立 Google Maps 連結
                maps_query = quote_plus(f"{title} {address}")
                maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"

                column = CarouselColumn(
                    title=title,
                    text=address,
                    actions=[
                        URIAction(
                            label='在地圖上查看',
                            uri=maps_url
                        )
                    ]
                )
                columns.append(column)
            except Exception as e:
                logger.error(f"Error creating carousel column for place {place.get('displayName')}: {e}")
                continue
        return TemplateMessage(alt_text='地點搜尋結果', template=CarouselTemplate(columns=columns)) if columns else TextMessage(text="抱歉，無法生成地點資訊卡片。")

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
            # 改善關鍵字提取邏輯，移除贅詞並處理空關鍵字
            keyword = re.sub(r'^(尋找|搜尋)|附近|的', '', user_message).strip()
            if not keyword:
                self._reply_error(line_bot_api, reply_token, "請告訴我要尋找什麼喔！\n格式：`尋找附近的餐廳`")
                return
            
            self.storage_service.set_nearby_query(user_id, keyword)
            self._reply_error(line_bot_api, reply_token, f"好的，請分享您的位置，我將為您尋找附近的「{keyword}」。")
        else:
            # 將一般搜尋也改為非同步模式，避免 reply token 逾時
            query = re.sub(r'^(尋找|搜尋)', '', user_message).strip()
            if not query:
                self._reply_error(line_bot_api, reply_token, "請告訴我要搜尋什麼喔！\n格式：`搜尋台北101`")
                return

            def task():
                """在背景執行緒中處理耗時的一般地點搜尋"""
                try:
                    places = self.ai_service.search_location(query)
                    if places and places.get("places"):
                        carousel = self._create_location_carousel(places["places"])
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[carousel]))
                    else:
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"抱歉，找不到關於「{query}」的地點資訊。")]))
                except Exception as e:
                    logger.error(f"Error in non-nearby search background task for user {user_id}: {e}", exc_info=True)
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，搜尋地點時發生錯誤了，請稍後再試。")]))

            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"收到指令！正在為您搜尋「{query}」...")])
            )
            threading.Thread(target=task).start()

class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""

    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        message_id = event.message.id
        logger.info(f"Received image message from user {user_id}, message_id: {message_id}")

        def task():
            """在背景執行緒中處理耗時的圖片分析任務"""
            try:
                # 1. 下載圖片 (核心修正)
                # 使用 MessagingApiBlob 來下載圖片內容，它需要從 api_client 實例化
                line_bot_api_blob = MessagingApiBlob(line_bot_api.api_client)
                message_content = line_bot_api_blob.get_message_content(message_id=message_id)
                image_bytes = message_content
                
                # 2. 進行 AI 分析
                analysis_result = self.ai_service.analyze_image(image_bytes)
                
                # 3. 推送分析結果
                line_bot_api.push_message(
                    PushMessageRequest(to=user_id, messages=[TextMessage(text=analysis_result)])
                )
            except Exception as e:
                logger.error(f"Error in image analysis background task for user {user_id}: {e}", exc_info=True)
                try:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，分析圖片時發生了一點問題，請稍後再試一次。")]))
                except Exception as push_e:
                    logger.error(f"Failed to push error message to user {user_id}: {push_e}", exc_info=True)

        # 立即回覆使用者，告知已收到圖片
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的圖片，正在為您分析...")])
        )
        # 啟動背景任務
        threading.Thread(target=task).start()

class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""

    # 修正 type hint，傳入的 event 是 MessageEvent，其 message 屬性才是 LocationMessageContent
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        latitude = event.message.latitude
        longitude = event.message.longitude
        logger.info(f"Received location from user {user_id}: Lat={latitude}, Lon={longitude}")

        pending_query = self.storage_service.get_nearby_query(user_id)
        if not pending_query:
            self._reply_error(line_bot_api, reply_token, "感謝您分享位置！如果您想搜尋附近的地點，可以先傳送「尋找附近的美食」喔！")
            return

        def task():
            """在背景執行緒中處理耗時的附近地點搜尋"""
            try:
                places = self.ai_service.search_location(query=pending_query, is_nearby=True, latitude=latitude, longitude=longitude)
                if places and places.get("places"):
                    carousel = self._create_location_carousel(places["places"])
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[carousel]))
                else:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"抱歉，在您附近找不到「{pending_query}」的相關地點。")]))
            except Exception as e:
                logger.error(f"Error in location search background task for user {user_id}: {e}", exc_info=True)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，搜尋附近地點時發生錯誤了，請稍後再試。")]))

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"收到您的位置！正在為您尋找附近的「{pending_query}」...")])
        )
        threading.Thread(target=task).start()