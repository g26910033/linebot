"""
訊息處理器模組
負責處理不同類型的 LINE 訊息，包含文字、圖片、位置等。
"""
import threading
import re
import requests
import json
import time
from urllib.parse import quote_plus
from datetime import datetime
from urllib3.exceptions import ProtocolError

from linebot.v3.messaging import (
    MessagingApi, MessagingApiBlob,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage, TemplateMessage,
    CarouselTemplate, CarouselColumn, URIAction,
    QuickReply, QuickReplyItem, MessageAction as QuickReplyMessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent, PostbackEvent
from services.ai_service import AIService
from services.web_service import WebService
from services.storage_service import StorageService
from services.utility_service import UtilityService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.calendar_service import CalendarService
from services.stock_service import StockService
from utils.logger import get_logger

logger = get_logger(__name__)

class MessageHandler:
    """訊息處理器基類。"""
    def __init__(self, ai_service: AIService, storage_service: StorageService, web_service: WebService = None, utility_service: UtilityService = None, weather_service: WeatherService = None, news_service: NewsService = None, calendar_service: CalendarService = None, stock_service: StockService = None) -> None:
        self.ai_service = ai_service
        self.storage_service = storage_service
        self.web_service = web_service
        self.utility_service = utility_service
        self.weather_service = weather_service
        self.news_service = news_service
        self.calendar_service = calendar_service
        self.stock_service = stock_service
        self.line_channel_access_token = None

    def _show_loading_animation(self, user_id: str, seconds: int = 10):
        if not self.line_channel_access_token:
            logger.warning("LINE Channel Access Token not set. Skipping loading animation.")
            return
        url = "https://api.line.me/v2/bot/chat/loading/start"
        headers = {"Authorization": f"Bearer {self.line_channel_access_token}", "Content-Type": "application/json"}
        data = {"chatId": user_id, "loadingSeconds": seconds}
        try:
            requests.post(url, headers=headers, json=data, timeout=5)
        except requests.RequestException as e:
            logger.error(f"Exception when showing loading animation: {e}")

    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        logger.error(f"Replying with error: {error_message}")
        self._reply_message(line_bot_api, reply_token, error_message)

    def _reply_message(self, line_bot_api: MessagingApi, reply_token: str, message: str) -> None:
        for attempt in range(3):
            try:
                api_response = line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)])
                )
                if api_response.status_code == 200:
                    return
                else:
                    logger.warning(f"Reply attempt {attempt + 1} failed with status {api_response.status_code}. Retrying...")
            except (requests.RequestException, ProtocolError) as e:
                logger.warning(f"Reply attempt {attempt + 1} failed with network error: {e}. Retrying...")
            time.sleep(0.5)
        logger.error(f"Failed to send reply message to {reply_token} after 3 attempts.")

    def _reply_flex_message(self, reply_token: str, flex_message_dict: dict, alt_text: str) -> None:
        if not self.line_channel_access_token:
            logger.error("Cannot send Flex Message: LINE Channel Access Token not set.")
            return
        
        url = "https://api.line.me/v2/bot/message/reply"
        headers = {
            "Authorization": f"Bearer {self.line_channel_access_token}",
            "Content-Type": "application/json"
        }
        message_data = {
            "type": "flex",
            "altText": alt_text,
            "contents": flex_message_dict
        }
        data = {
            "replyToken": reply_token,
            "messages": [message_data]
        }
        
        for attempt in range(3):
            try:
                response = requests.post(url, headers=headers, data=json.dumps(data), timeout=10)
                if response.status_code == 200:
                    return
                else:
                    logger.warning(f"Flex reply attempt {attempt + 1} failed with status {response.status_code}. Retrying...")
            except requests.RequestException as e:
                logger.warning(f"Flex reply attempt {attempt + 1} failed with network error: {e}. Retrying...")
            time.sleep(0.5)
        logger.error(f"Failed to send Flex Message to {reply_token} after 3 attempts.")

    def _create_location_carousel(self, places_list: list) -> TemplateMessage | TextMessage:
        columns = []
        for place in places_list[:10]:
            try:
                title = place.get('displayName', {}).get('text', '地點資訊')[:40]
                address = place.get('formattedAddress', '地址未提供')[:60]
                maps_query = quote_plus(f"{title} {address}")
                maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                columns.append(CarouselColumn(title=title, text=address, actions=[URIAction(label='在地圖上查看', uri=maps_url)]))
            except Exception as e:
                logger.error(f"Error creating carousel column for place {place.get('displayName')}: {e}")
                continue
        return TemplateMessage(alt_text='地點搜尋結果', template=CarouselTemplate(columns=columns)) if columns else TextMessage(text="抱歉，無法生成地點資訊卡片。")

class TextMessageHandler(MessageHandler):
    _URL_PATTERN = re.compile(r'https?://\S+')

    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        user_message = event.message.text.strip()
        logger.info(f"Received text message from user {user_id}: '{user_message}'")

        try:
            if self.utility_service:
                conversion_result = self.utility_service.parse_and_convert(user_message, self.ai_service)
                if conversion_result:
                    logger.debug(f"User {user_id} triggered unit/currency conversion.")
                    self._reply_message(line_bot_api, reply_token, conversion_result)
                    return

            if self.weather_service:
                weather_query = self.ai_service.parse_weather_query_from_text(user_message)
                if weather_query and weather_query.get("city"):
                    city = weather_query["city"]
                    query_type = weather_query.get("type", "current")
                    self._show_loading_animation(user_id)
                    def weather_task(user_id, city, query_type):
                        if query_type == "forecast":
                            forecast_result = self.weather_service.get_weather_forecast(city)
                            if isinstance(forecast_result, dict):
                                carousel = self._create_weather_forecast_carousel(forecast_result)
                                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[carousel]))
                            else:
                                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=forecast_result)]))
                        else:
                            current_weather = self.weather_service.get_current_weather(city)
                            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=current_weather)]))
                    threading.Thread(target=weather_task, args=(user_id, city, query_type)).start()
                    return

            if self.news_service and self._is_news_command(user_message):
                self._show_loading_animation(user_id)
                def news_task(user_id):
                    news_result = self.news_service.get_top_headlines()
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=news_result)]))
                threading.Thread(target=news_task, args=(user_id,)).start()
                return

            if self.stock_service:
                symbol = self.ai_service.parse_stock_symbol_from_text(user_message)
                if symbol:
                    self._show_loading_animation(user_id)
                    def stock_task(user_id, symbol):
                        stock_result = self.stock_service.get_stock_quote(symbol)
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=stock_result)]))
                    threading.Thread(target=stock_task, args=(user_id, symbol)).start()
                    return

            if self._is_translation_command(user_message):
                self._show_loading_animation(user_id)
                def translation_task(user_id, user_message):
                    translated_text = self.ai_service.translate_text(user_message)
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=translated_text)]))
                threading.Thread(target=translation_task, args=(user_id, user_message)).start()
                return

            if self.calendar_service and self._is_calendar_command(user_message):
                self._show_loading_animation(user_id)
                def calendar_task(user_id, user_message):
                    event_data = self.ai_service.parse_event_from_text(user_message)
                    if not event_data or not event_data.get('title'):
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，我無法理解您的行程安排，可以說得更清楚一點嗎？")]))
                        return
                    calendar_link = self.calendar_service.create_google_calendar_link(event_data)
                    if not calendar_link:
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，處理您的日曆請求時發生錯誤。")]))
                        return
                    reply_text = (f"好的，我為您準備好日曆連結了！\n\n"
                                  f"標題：{event_data.get('title')}\n"
                                  f"時間：{event_data.get('start_time')}\n\n"
                                  f"請點擊下方連結將它加入您的 Google 日曆：\n{calendar_link}")
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=reply_text)]))
                threading.Thread(target=calendar_task, args=(user_id, user_message)).start()
                return

            if self._is_help_command(user_message):
                self._handle_help(reply_token, line_bot_api)
                return

            if user_message == "天氣/新聞":
                quick_reply = QuickReply(items=[
                    QuickReplyItem(action=QuickReplyMessageAction(label="🌦️ 看天氣", text="今天天氣如何")),
                    QuickReplyItem(action=QuickReplyMessageAction(label="📰 看新聞", text="頭條新聞"))
                ])
                line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="請問您想看天氣還是新聞？", quick_reply=quick_reply)]))
                return
            
            if user_message == "圖片功能":
                self._reply_message(line_bot_api, reply_token, "請先上傳一張圖片，然後點選「圖片分析」或「以圖生圖」按鈕喔！")
                return

            if user_message == "[指令]圖片分析":
                self._handle_image_analysis(user_id, reply_token, line_bot_api)
                return
            
            if user_message == "[指令]以圖生圖":
                self._handle_image_to_image_init(user_id, reply_token, line_bot_api)
                return

            user_state = self.storage_service.get_user_state(user_id)
            if user_state == "waiting_image_prompt":
                self._handle_image_to_image_prompt(user_id, user_message, reply_token, line_bot_api)
                return

            if self._is_draw_command(user_message):
                prompt = user_message.replace("畫", "", 1).strip()
                self._handle_draw_command(prompt, user_id, reply_token, line_bot_api)
            elif self._is_clear_history_command(user_message):
                self._handle_clear_history(user_id, reply_token, line_bot_api)
            elif self._is_search_command(user_message):
                self._handle_search_command(user_message, user_id, reply_token, line_bot_api)
            elif self._is_add_todo_command(user_message):
                item = re.sub(r'^(新增待辦|todo)', '', user_message, flags=re.IGNORECASE).strip()
                self._handle_add_todo(item, user_id, reply_token, line_bot_api)
            elif self._is_list_todo_command(user_message):
                self._handle_list_todos(user_id, reply_token, line_bot_api)
            elif self._is_complete_todo_command(user_message):
                match = re.search(r'\d+', user_message)
                item_index = int(match.group(0)) - 1 if match else -1
                self._handle_complete_todo(item_index, user_id, reply_token, line_bot_api)
            elif self._is_url_message(user_message):
                self._handle_url_message(user_message, user_id, reply_token, line_bot_api)
            else:
                self._show_loading_animation(user_id)
                def chat_task(user_id, user_message):
                    try:
                        history = self.storage_service.get_chat_history(user_id)
                        ai_response, updated_history = self.ai_service.chat_with_history(user_message, history)
                        self.storage_service.save_chat_history(user_id, updated_history)
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=ai_response)]))
                    except Exception as e:
                        logger.error(f"Error in chat background task for user {user_id}: {e}", exc_info=True)
                        try:
                            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，處理您的訊息時發生了一點問題，請稍後再試一次。")]))
                        except Exception as push_e:
                            logger.error(f"Failed to push error message to user {user_id}: {push_e}", exc_info=True)
                threading.Thread(target=chat_task, args=(user_id, user_message)).start()
        except Exception as e:
            logger.error(f"Error handling text message for user {user_id}: {e}", exc_info=True)
            self._reply_error(line_bot_api, reply_token, "處理您的訊息時發生了未預期的錯誤，請稍後再試。")

    def _is_draw_command(self, text: str) -> bool: return text.startswith("畫")
    def _is_clear_history_command(self, text: str) -> bool: return text in ["清除對話", "忘記對話", "清除記憶"]
    def _is_search_command(self, text: str) -> bool: return text.startswith("搜尋") or text.startswith("尋找")
    def _is_add_todo_command(self, text: str) -> bool: return text.lower().startswith("新增待辦") or text.lower().startswith("todo")
    def _is_list_todo_command(self, text: str) -> bool: return text in ["待辦清單", "我的待辦", "todo list"]
    def _is_complete_todo_command(self, text: str) -> bool: return text.lower().startswith("完成待辦") or text.lower().startswith("done")
    def _is_url_message(self, text: str) -> bool: return self._URL_PATTERN.match(text) is not None
    def _is_news_command(self, text: str) -> bool: return any(keyword in text.lower() for keyword in ["新聞", "頭條"])
    def _is_translation_command(self, text: str) -> bool: return any(keyword in text.lower() for keyword in ["翻譯", "翻成"])
    def _is_calendar_command(self, text: str) -> bool: return any(keyword in text.lower() for keyword in ["提醒我", "新增日曆", "新增行程", "的日曆"])
    def _is_help_command(self, text: str) -> bool: return text in ["功能說明", "help", "幫助", "指令"]

    def handle_postback(self, event: PostbackEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        postback_data = event.postback.data
        logger.info(f"Received postback from user {user_id}: '{postback_data}'")
        try:
            params = dict(p.split('=') for p in postback_data.split('&'))
            action = params.get('action')
            if action == 'complete_todo':
                item_index = int(params.get('index', -1))
                if item_index >= 0:
                    removed_item = self.storage_service.remove_todo_item(user_id, item_index)
                    if removed_item:
                        self._reply_message(line_bot_api, reply_token, f"太棒了！已完成項目：「{removed_item}」")
                        updated_todo_list = self.storage_service.get_todo_list(user_id)
                        if updated_todo_list:
                            flex_message_dict = self._create_todo_list_flex_message(updated_todo_list)
                            logger.info("Pushing updated todo list via raw API call would happen here.")
                        else:
                            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="恭喜！所有待辦事項都已完成！")]))
                    else:
                        self._reply_error(line_bot_api, reply_token, "抱歉，找不到指定的待辦事項，可能已經被移除了。")
            else:
                logger.warning(f"Unhandled postback action '{action}' from user {user_id}")
        except Exception as e:
            logger.error(f"Error handling postback for user {user_id}: {e}", exc_info=True)
            self._reply_error(line_bot_api, reply_token, "處理您的操作時發生了錯誤。")

    def _handle_help(self, reply_token: str, line_bot_api: MessagingApi) -> None:
        help_text = """
您好！這是一個功能強大的 AI 助理，您可以這樣使用我：

🤖【AI 對話】
直接輸入任何文字，開始與我對話。

🎨【AI 繪圖】
- `畫 一隻貓`：基本文字生圖。
- 上傳圖片後點選「以圖生圖」，再輸入提示詞（如：`讓牠變成賽博龐克風格`），即可修改圖片。

🖼️【圖片分析】
上傳圖片後，點選「圖片分析」。

📍【地點搜尋】
- `搜尋 台北101`
- `尋找附近的咖啡廳` (需分享位置)

🌦️【天氣查詢】
- `今天台北天氣如何`
- `未來幾天東京的天氣預報`

📰【新聞頭條】
- `新聞` 或 `頭條`

📈【股市查詢】
- `台積電股價` 或 `我想知道TSLA的股價`

✅【互動待辦清單】
- `新增待辦 買牛奶`
- `我的待辦` (會顯示可點擊的清單)

【單位/匯率換算】
- `100公分等於幾公尺`
- `50 USD to TWD`
- `一百台幣多少美元`

📅【新增日曆行程】
- `提醒我明天下午3點開會`
- `新增日曆下週五去看電影`

🌐【網頁/YouTube 影片摘要】
直接貼上網址連結或 YouTube 影片連結。

🗣️【多語言翻譯】
- `翻譯 你好到英文`

🧹【清除對話紀錄】
- `清除對話`
        """
        self._reply_message(line_bot_api, reply_token, help_text.strip())

    def _handle_image_analysis(self, user_id: str, reply_token: str, line_bot_api: MessagingApi):
        message_id = self.storage_service.get_user_last_image_id(user_id)
        if not message_id:
            self._reply_message(line_bot_api, reply_token, "抱歉，找不到您剛才傳的圖片，請再試一次。")
            return
        self._show_loading_animation(user_id)
        def task(user_id):
            try:
                line_bot_api_blob = MessagingApiBlob(line_bot_api.api_client)
                image_bytes = line_bot_api_blob.get_message_content(message_id=message_id)
                analysis_result = self.ai_service.analyze_image(image_bytes)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=analysis_result)]))
            except Exception as e:
                logger.error(f"Error in image analysis task for user {user_id}: {e}", exc_info=True)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="分析圖片時發生錯誤了。")]))
        threading.Thread(target=task, args=(user_id,)).start()

    def _handle_image_to_image_init(self, user_id: str, reply_token: str, line_bot_api: MessagingApi):
        message_id = self.storage_service.get_user_last_image_id(user_id)
        if not message_id:
            self._reply_message(line_bot_api, reply_token, "抱歉，找不到您剛才傳的圖片，請再試一次。")
            return
        self.storage_service.set_user_state(user_id, "waiting_image_prompt")
        self._reply_message(line_bot_api, reply_token, "好的，請告訴我要如何修改這張圖片？\n（例如：`讓它變成梵谷風格`、`加上一頂帽子`）")

    def _handle_image_to_image_prompt(self, user_id: str, prompt: str, reply_token: str, line_bot_api: MessagingApi):
        message_id = self.storage_service.get_user_last_image_id(user_id)
        if not message_id:
            self._reply_message(line_bot_api, reply_token, "抱歉，找不到您剛才傳的圖片，請重新上傳一次。")
            return
        self._show_loading_animation(user_id, seconds=30)
        def task(user_id, prompt):
            try:
                line_bot_api_blob = MessagingApiBlob(line_bot_api.api_client)
                base_image_bytes = line_bot_api_blob.get_message_content(message_id=message_id)
                new_image_bytes, status_msg = self.ai_service.generate_image_from_image(base_image_bytes, prompt)
                if new_image_bytes:
                    image_url, upload_status = self.storage_service.upload_image_to_cloudinary(new_image_bytes)
                    if image_url:
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)]))
                    else:
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"圖片上傳失敗: {upload_status}")]))
                else:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"繪圖失敗: {status_msg}")]))
            except Exception as e:
                logger.error(f"Error in image-to-image task for user {user_id}: {e}", exc_info=True)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="以圖生圖時發生錯誤了。")]))
        threading.Thread(target=task, args=(user_id, prompt)).start()

    def _handle_draw_command(self, prompt: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not prompt:
            self._reply_message(line_bot_api, reply_token, "請告訴我要畫什麼喔！\n格式：`畫 一隻可愛的貓`")
            return
        self._show_loading_animation(user_id, seconds=30)
        def task(user_id, prompt):
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
        threading.Thread(target=task, args=(user_id, prompt)).start()

    def _handle_clear_history(self, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        self.storage_service.clear_chat_history(user_id)
        self._reply_message(line_bot_api, reply_token, "好的，我們的對話記憶已經清除！")

    def _handle_search_command(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if "附近" in user_message:
            keyword = re.sub(r'^(尋找|搜尋)|附近|的', '', user_message, flags=re.IGNORECASE).strip()
            if not keyword:
                self._reply_message(line_bot_api, reply_token, "請告訴我要尋找什麼喔！\n格式：`尋找附近的餐廳`")
                return
            self.storage_service.set_nearby_query(user_id, keyword)
            self._reply_message(line_bot_api, reply_token, f"好的，請分享您的位置，我將為您尋找附近的「{keyword}」。")
        else:
            query = re.sub(r'^(尋找|搜尋)', '', user_message, flags=re.IGNORECASE).strip()
            if not query:
                self._reply_message(line_bot_api, reply_token, "請告訴我要搜尋什麼喔！\n格式：`搜尋台北101`")
                return
            self._show_loading_animation(user_id)
            def task(user_id, query):
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
            threading.Thread(target=task, args=(user_id, query)).start()

    def _handle_url_message(self, user_message: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not self.web_service:
            self._reply_message(line_bot_api, reply_token, "抱歉，網頁/影片摘要服務目前未啟用。")
            return
        url_match = re.search(r'https?://\S+', user_message)
        if not url_match:
            self._reply_message(line_bot_api, reply_token, "抱歉，訊息中未包含有效的網址。")
            return
        url = url_match.group(0)
        
        self._show_loading_animation(user_id, seconds=30)

        def task(user_id, url):
            try:
                content = self.web_service.fetch_url_content(url)
                if not content:
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，無法讀取您提供的網址內容。")]))
                    return
                
                summary = self.ai_service.summarize_text(content)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=summary)]))
            except Exception as e:
                logger.error(f"Error in URL message handling task for user {user_id}: {e}", exc_info=True)
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="哎呀，摘要網頁/影片內容時發生錯誤了，請稍後再試。")]))
        threading.Thread(target=task, args=(user_id, url)).start()

    def _handle_add_todo(self, item: str, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if not item:
            self._reply_message(line_bot_api, reply_token, "請告訴我要新增什麼待辦事項喔！\n格式：`新增待辦 買牛奶`")
            return
        if self.storage_service.add_todo_item(user_id, item):
            self._reply_message(line_bot_api, reply_token, f"好的，已將「{item}」加入您的待辦清單！")
        else:
            self._reply_error(line_bot_api, reply_token, "抱歉，新增待辦事項時發生錯誤。")

    def _handle_list_todos(self, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        todo_list = self.storage_service.get_todo_list(user_id)
        if not todo_list:
            self._reply_message(line_bot_api, reply_token, "您的待辦清單是空的！")
        else:
            flex_message_dict = self._create_todo_list_flex_message(todo_list)
            self._reply_flex_message(reply_token, flex_message_dict, "您的待辦清單")

    def _handle_complete_todo(self, item_index: int, user_id: str, reply_token: str, line_bot_api: MessagingApi) -> None:
        if item_index < 0:
            self._reply_message(line_bot_api, reply_token, "請告訴我要完成哪一項喔！\n格式：`完成待辦 1`")
            return
        removed_item = self.storage_service.remove_todo_item(user_id, item_index)
        if removed_item is not None:
            self._reply_message(line_bot_api, reply_token, f"太棒了！已完成項目：「{removed_item}」")
        else:
            self._reply_error(line_bot_api, reply_token, "找不到您指定的待辦事項，請檢查編號是否正確。")

    def _create_todo_list_flex_message(self, todo_list: list) -> dict:
        body_contents = []
        for i, item in enumerate(todo_list[:10]):
            body_contents.append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{i+1}. {item}",
                        "wrap": True,
                        "flex": 4
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "完成",
                            "data": f"action=complete_todo&index={i}",
                            "displayText": f"完成待辦 {i+1}"
                        },
                        "style": "primary",
                        "color": "#1DB446",
                        "height": "sm",
                        "flex": 1
                    }
                ]
            })
            if i < len(todo_list[:10]) - 1:
                body_contents.append({"type": "separator", "margin": "md"})

        if len(todo_list) > 10:
            body_contents.append({"type": "separator", "margin": "md"})
            body_contents.append({
                "type": "text",
                "text": f"...還有 {len(todo_list) - 10} 個項目未顯示。",
                "size": "sm",
                "color": "#999999",
                "wrap": True
            })
        
        return {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "📝 您的待辦清單",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#1DB446"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": body_contents
            }
        }

    def _create_weather_forecast_carousel(self, forecast_data: dict) -> TemplateMessage:
        city_name = forecast_data.get("city", "未知城市")
        columns = []
        for daily_data in forecast_data.get("forecasts", []):
            date = datetime.fromtimestamp(daily_data['dt'])
            date_str = date.strftime('%m/%d')
            weekday_str = ["一", "二", "三", "四", "五", "六", "日"][date.weekday()]
            icon_url = f"https://openweathermap.org/img/wn/{daily_data['icon']}@2x.png"
            column = CarouselColumn(
                thumbnail_image_url=icon_url,
                title=f"{date_str} (週{weekday_str})",
                text=f"{daily_data['description']}\n溫度: {daily_data['temp_min']:.0f}°C - {daily_data['temp_max']:.0f}°C",
                actions=[URIAction(label='查看詳情', uri=f"https://www.google.com/search?q={quote_plus(f'{city_name} 天氣')}")]
            )
            columns.append(column)
        return TemplateMessage(alt_text=f'{city_name} 的天氣預報', template=CarouselTemplate(columns=columns[:10]))

class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        message_id = event.message.id
        logger.info(f"Received image message from user {user_id}, message_id: {message_id}")
        quick_reply_buttons = QuickReply(items=[
            QuickReplyItem(action=QuickReplyMessageAction(label="🔍 圖片分析", text="[指令]圖片分析")),
            QuickReplyItem(action=QuickReplyMessageAction(label="🎨 以圖生圖", text="[指令]以圖生圖")),
        ])
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的圖片了！請問您想做什麼？", quick_reply=quick_reply_buttons)]))
        def task(user_id, message_id):
            try:
                self.storage_service.set_user_last_image_id(user_id, message_id)
                logger.info(f"Saved image message_id {message_id} for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to save image message_id for user {user_id}: {e}", exc_info=True)
        threading.Thread(target=task, args=(user_id, message_id)).start()

class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        user_id = event.source.user_id
        reply_token = event.reply_token
        latitude = event.message.latitude
        longitude = event.message.longitude
        logger.info(f"Received location from user {user_id}: Lat={latitude}, Lon={longitude}")
        pending_query = self.storage_service.get_nearby_query(user_id)
        if not pending_query:
            self._reply_message(line_bot_api, reply_token, "感謝您分享位置！如果您想搜尋附近的地點，可以先傳送「尋找附近的美食」喔！")
            return
        self._show_loading_animation(user_id)
        def task(user_id, pending_query, latitude, longitude):
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
        threading.Thread(target=task, args=(user_id, pending_query, latitude, longitude)).start()
