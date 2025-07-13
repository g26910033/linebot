"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
import re
import requests
from urllib.parse import quote_plus
from linebot.v3.messaging import (
    MessagingApi, MessagingApiBlob,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage, TemplateMessage,
    CarouselTemplate, CarouselColumn, URIAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent
from services.ai_service import AIService
from services.web_service import WebService
from services.storage_service import StorageService
from services.utility_service import UtilityService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.calendar_service import CalendarService
from utils.logger import get_logger

logger = get_logger(__name__)

class MessageHandler:
    """訊息處理器基類。"""
    def __init__(self, ai_service: AIService, storage_service: StorageService, web_service: WebService = None, utility_service: UtilityService = None, weather_service: WeatherService = None, news_service: NewsService = None, calendar_service: CalendarService = None) -> None:
        self.ai_service = ai_service
        self.storage_service = storage_service
        self.web_service = web_service
        self.utility_service = utility_service
        self.weather_service = weather_service
        self.news_service = news_service
        self.calendar_service = calendar_service
        self.line_channel_access_token = None # 稍後在 app.py 中設定

    def _show_loading_animation(self, user_id: str, seconds: int = 10):
        """顯示 LINE 的載入中動畫"""
        if not self.line_channel_access_token:
            logger.warning("LINE Channel Access Token not set. Skipping loading animation.")
            return

        url = "https://api.line.me/v2/bot/chat/loading/start"
        headers = {
            "Authorization": f"Bearer {self.line_channel_access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "chatId": user_id,
            "loadingSeconds": seconds
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=5)
            if response.status_code != 202:
                logger.error(f"Failed to show loading animation. Status: {response.status_code}, Body: {response.text}")
        except requests.RequestException as e:
            logger.error(f"Exception when showing loading animation: {e}")

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

    _URL_PATTERN = re.compile(r'https?://\S+')

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
            # 檢查是否為單位換算指令
            if self.utility_service:
                conversion_result = self.utility_service.parse_and_convert(user_message)
                if conversion_result:
                    logger.debug(f"User {user_id} triggered unit conversion.")
                    self._reply_error(line_bot_api, reply_token, conversion_result)
                    return

            # 檢查是否為天氣查詢指令
            if self.weather_service and self._is_weather_command(user_message):
                city = user_message.replace("天氣", "").strip()
                if city:
                    logger.debug(f"User {user_id} triggered weather command for city: {city}")
                    weather_result = self.weather_service.get_weather(city)
                    self._reply_error(line_bot_api, reply_token, weather_result)
                    return
                else:
                    self._reply_error(line_bot_api, reply_token, "請告訴我想查詢哪個城市的天氣喔！\n格式：`台北天氣`")
                    return

            # 檢查是否為新聞查詢指令
            if self.news_service and self._is_news_command(user_message):
                logger.debug(f"User {user_id} triggered news command.")
                news_result = self.news_service.get_top_headlines()
                self._reply_error(line_bot_api, reply_token, news_result)
                return

            # 檢查是否為翻譯指令
            if self._is_translation_command(user_message):
                logger.debug(f"User {user_id} triggered translation command.")
                self._handle_translation(user_message, reply_token, line_bot_api)
                return

            # 檢查是否為日曆指令
            if self.calendar_service and self._is_calendar_command(user_message):
                logger.debug(f"User {user_id} triggered calendar command.")
                self._handle_calendar_command(user_message, reply_token, line_bot_api)
                return

            # 檢查是否為功能說明指令
            if self._is_help_command(user_message):
                logger.debug(f"User {user_id} triggered help command.")
                self._handle_help(reply_token, line_bot_api)
                return

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
            elif self._is_add_todo_command(user_message):
                logger.debug(f"User {user_id} triggered add todo command.")
                item = re.sub(r'^(新增待辦|todo)', '', user_message, flags=re.IGNORECASE).strip()
                self._handle_add_todo(item, user_id, reply_token, line_bot_api)
            elif self._is_list_todo_command(user_message):
                logger.debug(f"User {user_id} triggered list todo command.")
                self._handle_list_todos(user_id, reply_token, line_bot_api)
            elif self._is_complete_todo_command(user_message):
                logger.debug(f"User {user_id} triggered complete todo command.")
                match = re.search(r'\d+', user_message)
                item_index = int(match.group(0)) - 1 if match else -1
                self._handle_complete_todo(item_index, user_id, reply_token, line_bot_api)
            elif self._is_url_message(user_message):
                logger.debug(f"User {user_id} sent a URL.")
                self._handle_url_message(user_message, user_id, reply_token, line_bot_api)
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

    def _is_add_todo_command(self, text: str) -> bool:
        return text.lower().startswith("新增待辦") or text.lower().startswith("todo")

    def _is_list_todo_command(self, text: str) -> bool:
        return text in ["待辦清單", "我的待辦", "todo list"]

    def _is_complete_todo_command(self, text: str) -> bool:
        return text.lower().startswith("完成待辦") or text.lower().startswith("done")

    def _is_url_message(self, text: str) -> bool:
        return self._URL_PATTERN.match(text) is not None

    def _is_weather_command(self, text: str) -> bool:
        return text.endswith("天氣")

    def _is_news_command(self, text: str) -> bool:
        # 放寬判斷條件，檢查是否包含關鍵字
        keywords = ["新聞", "頭條"]
        return any(keyword in text.lower() for keyword in keywords)

    def _is_translation_command(self, text: str) -> bool:
        return text.lower().startswith("翻譯")

    def _is_calendar_command(self, text: str) -> bool:
        # 放寬判斷條件，檢查是否包含關鍵字
        keywords = ["提醒我", "新增日曆", "新增行程", "的日曆"]
        return any(keyword in text.lower() for keyword in keywords)

    def _is_help_command(self, text: str) -> bool:
        return text in ["功能說明", "help", "幫助", "指令"]

    def _handle_help(self, reply_token: str, line_bot_api: MessagingApi) -> None:
        help_text = """
您好！這是一個功能強大的 AI 助理，您可以這樣使用我：

🤖【AI 對話】
直接輸入任何文字，開始與我對話。

🎨【AI 繪圖】
開頭說「畫」，例如：
`畫一隻在月球上喝茶的貓`

🖼️【圖片分析】
直接傳送任何圖片給我。

📍【地點搜尋】
- `搜尋 台北101`
- `尋找附近的咖啡廳` (需分享位置)

🌦️【天氣查詢】
- `台北天氣`

📰【新聞頭條】
- `新聞` 或 `頭條`

💱【單位/匯率換算】
- `100公分等於幾公尺`
- `50 USD to TWD`

📅【新增日曆行程】
- `提醒我明天下午3點開會`
- `新增日曆下週五去看電影`

🌐【網頁文章摘要】
直接貼上網址連結。

🗣️【多語言翻譯】
- `翻譯 你好到英文`

🧹【清除對話紀錄】
- `清除對話`
        """
        self._reply_error(line_bot_api, reply_token, help_text.strip())

    def _handle_calendar_command(self, user_message: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        # 讓 AI 解析文字
        event_data = self.ai_service.parse_event_from_text(user_message)

        if not event_data or not event_data.get('title'):
            self._reply_error(line_bot_api, reply_token, "抱歉，我無法理解您的行程安排，可以說得更清楚一點嗎？")
            return

        # 產生 Google 日曆連結
        calendar_link = self.calendar_service.create_google_calendar_link(event_data)

        if not calendar_link:
            self._reply_error(line_bot_api, reply_token, "抱歉，處理您的日曆請求時發生錯誤。")
            return
        
        reply_text = (
            f"好的，我為您準備好日曆連結了！\n\n"
            f"標題：{event_data.get('title')}\n"
            f"時間：{event_data.get('start_time')}\n\n"
            f"請點擊下方連結將它加入您的 Google 日曆：\n{calendar_link}"
        )
        self._reply_error(line_bot_api, reply_token, reply_text)

    def _handle_translation(self, user_message: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        # 使用正則表達式解析指令，例如 "翻譯 你好 到 英文"
        match = re.match(r'翻譯\s+(.+?)\s+(?:到|成)\s+(.+)', user_message, re.IGNORECASE)
        if not match:
            self._reply_error(line_bot_api, reply_token, "翻譯指令格式不正確喔！\n請使用：`翻譯 [要翻譯的文字] 到 [目標語言]`\n例如：`翻譯 你好到英文`")
            return

        text_to_translate, target_language = match.groups()
        
        # 進行翻譯
        translated_text = self.ai_service.translate_text(text_to_translate.strip(), target_language.strip())
        
        # 回覆結果
        self._reply_error(line_bot_api, reply_token, translated_text)

    def _handle_chat(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        self._show_loading_animation(user_id)
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
        
        self._show_loading_animation(user_id, seconds=30) # 繪圖可能需要更長時間

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

    def _handle_url_message(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not self.web_service:
            self._reply_error(line_bot_api, reply_token, "抱歉，URL 處理服務目前未啟用。")
            return

        # 提取使用者訊息中的網址
        url = re.search(r'https?://\S+', user_message)
        if not url:
            self._reply_error(line_bot_api, reply_token, "抱歉，訊息中未包含有效的網址。")
            return

        url = url.group(0)

        def task():
            """在背景執行緒中處理耗時的網頁抓取與摘要任務"""
            content = self.web_service.fetch_url_content(url)
            if not content:
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，無法讀取您提供的網址內容。")]))
                return
            
            summary = self.ai_service.summarize_text(content)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=summary)]))

        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的網址，正在為您摘要文章內容...")])
        )
        threading.Thread(target=task).start()

    def _handle_add_todo(self, item: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not item:
            self._reply_error(line_bot_api, reply_token, "請告訴我要新增什麼待辦事項喔！\n格式：`新增待辦 買牛奶`")
            return
        if self.storage_service.add_todo_item(user_id, item):
            self._reply_error(line_bot_api, reply_token, f"好的，已將「{item}」加入您的待辦清單！")
        else:
            self._reply_error(line_bot_api, reply_token, "抱歉，新增待辦事項時發生錯誤。")

    def _handle_list_todos(self, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        todo_list = self.storage_service.get_todo_list(user_id)
        if not todo_list:
            reply_text = "您的待辦清單是空的！"
        else:
            items_text = "\n".join(f"{i+1}. {item}" for i, item in enumerate(todo_list))
            reply_text = f"您的待辦清單：\n{items_text}"
        self._reply_error(line_bot_api, reply_token, reply_text)

    def _handle_complete_todo(self, item_index: int, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if item_index < 0:
            self._reply_error(line_bot_api, reply_token, "請告訴我要完成哪一項喔！\n格式：`完成待辦 1`")
            return

        removed_item = self.storage_service.remove_todo_item(user_id, item_index)

        if removed_item is not None:
            self._reply_error(line_bot_api, reply_token, f"太棒了！已完成項目：「{removed_item}」")
        else:
            self._reply_error(line_bot_api, reply_token, "找不到您指定的待辦事項，請檢查編號是否正確。")


class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""

    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        message_id = event.message.id
        logger.info(f"Received image message from user {user_id}, message_id: {message_id}")
        
        self._show_loading_animation(user_id)

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
