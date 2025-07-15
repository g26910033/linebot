"""
中央指令處理器
"""
import os
import threading
import re
from urllib.parse import quote_plus
from datetime import datetime
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ImageMessage,
    TemplateMessage, CarouselTemplate, CarouselColumn, URIAction,
    PushMessageRequest, ReplyMessageRequest, QuickReply, QuickReplyItem,
    MessageAction as QuickReplyMessageAction)
from services.ai.core import AICoreService
from services.ai.parsing_service import AIParsingService
from services.ai.image_service import AIImageService
from services.ai.text_service import AITextService
from services.storage_service import StorageService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.calendar_service import CalendarService
from services.stock_service import StockService
from services.web_service import WebService
from utils.logger import get_logger

logger = get_logger(__name__)

class CentralHandler:
    def __init__(self, services: dict, configuration: Configuration):
        self.core_service: AICoreService = services['core']
        self.parsing_service: AIParsingService = services['parsing']
        self.image_service: AIImageService = services['image']
        self.text_service: AITextService = services['text']
        self.storage_service: StorageService = services['storage']
        self.weather_service: WeatherService = services['weather']
        self.news_service: NewsService = services['news']
        self.calendar_service: CalendarService = services['calendar']
        self.stock_service: StockService = services['stock']
        self.web_service: WebService = services['web']
        self.configuration = configuration

    def handle(self, event):
        user_id = event.source.user_id
        user_message = event.message.text.strip()
        reply_token = event.reply_token

        # 優先處理 URL
        if self.web_service.is_url(user_message):
            self._handle_url_message(user_id, user_message)
            return
        
        # 處理圖片相關的特殊指令
        if user_message == "[指令]圖片分析":
            self._handle_image_analysis_init(user_id, reply_token)
            return
        if user_message == "[指令]以圖生圖":
            self._handle_image_to_image_init(user_id, reply_token)
            return

        # 意圖解析
        intent_data = self.parsing_service.parse_intent_from_text(user_message)
        intent = intent_data.get("intent", "general_chat")
        data = intent_data.get("data", {})
        
        logger.info(f"Intent: {intent}, Data: {data}")

        # 根據意圖分派任務
        if intent == "image_features_options":
            self._handle_image_features_options(reply_token)
        elif intent == "show_weather_news_options":
            self._handle_show_weather_news_options(reply_token)
        elif intent == "weather":
            self._handle_weather(user_id, reply_token, data)
        elif intent == "stock":
            self._handle_stock(user_id, data)
        elif intent == "news":
            self._handle_news(user_id)
        elif intent == "calendar":
            self._handle_calendar(user_id, data)
        elif intent == "translation":
            self._handle_translation(user_id, data)
        elif intent == "nearby_search":
            self._handle_nearby_search(user_id, reply_token, data)
        elif intent == "help":
            self._handle_help(reply_token)
        elif intent == "draw":
            self._handle_draw(user_id, reply_token, data)
        elif intent == "clear_memory":
            self._handle_clear_memory(user_id, reply_token)
        else: # general_chat
            self._handle_chat(user_id, user_message)

    def _execute_in_background(self, func, *args):
        threading.Thread(target=func, args=args).start()

    def _push_message(self, user_id, messages):
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=messages))

    def _reply_message(self, reply_token, messages):
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))

    def _handle_url_message(self, user_id, url):
        def task():
            self._push_message(user_id, [TextMessage(text="收到您的網址了，正在為您分析摘要...")])
            content = self.web_service.fetch_url_content(url)
            if not content:
                summary = "抱歉，無法讀取這個網址的內容。"
            else:
                summary = self.text_service.summarize_text(content)
            self._push_message(user_id, [TextMessage(text=f"網址摘要：\n\n{summary}")])
        self._execute_in_background(task)

    def _handle_image_features_options(self, reply_token):
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=QuickReplyMessageAction(label="🔍 圖片分析", text="[指令]圖片分析")),
            QuickReplyItem(action=QuickReplyMessageAction(label="🎨 以圖生圖", text="[指令]以圖生圖")),
        ])
        self._reply_message(reply_token, [TextMessage(text="請問您想使用哪種圖片功能？", quick_reply=quick_reply)])

    def _handle_show_weather_news_options(self, reply_token):
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=QuickReplyMessageAction(label="🌦️ 看天氣", text="今天天氣如何")),
            QuickReplyItem(action=QuickReplyMessageAction(label="📰 看新聞", text="頭條新聞"))
        ])
        self._reply_message(reply_token, [TextMessage(text="請問您想看天氣還是新聞？", quick_reply=quick_reply)])

    def _handle_image_analysis_init(self, user_id, reply_token):
        self.storage_service.set_user_state(user_id, "waiting_for_analysis_image")
        self._reply_message(reply_token, [TextMessage(text="好的，請現在上傳您要分析的圖片。")])

    def _handle_image_to_image_init(self, user_id, reply_token):
        self.storage_service.set_user_state(user_id, "waiting_for_i2i_image")
        self._reply_message(reply_token, [TextMessage(text="好的，請先上傳您要做為基底的圖片。")])

    def _handle_weather(self, user_id, reply_token, data):
        city = data.get("city")
        if not city:
            self._reply_message(reply_token, [TextMessage(text="請告訴我您想查詢哪個城市的天氣喔！")])
            return
        query_type = data.get("type", "current")
        def task():
            if query_type == "forecast":
                forecast_data = self.weather_service.get_weather_forecast(city)
                message = TextMessage(text=forecast_data) if isinstance(forecast_data, str) else self._create_weather_forecast_carousel(forecast_data)
            else:
                result = self.weather_service.get_current_weather(city)
                message = TextMessage(text=result)
            self._push_message(user_id, [message])
        self._execute_in_background(task)

    def _handle_stock(self, user_id, data):
        symbol = data.get("symbol")
        if not symbol: return
        def task():
            result = self.stock_service.get_stock_quote(symbol)
            self._push_message(user_id, [TextMessage(text=result)])
        self._execute_in_background(task)

    def _handle_news(self, user_id):
        def task():
            formatted_news = self.news_service.get_top_headlines()
            self._push_message(user_id, [TextMessage(text=formatted_news)])
        self._execute_in_background(task)

    def _handle_calendar(self, user_id, data):
        def task():
            if not data or not data.get('title'):
                reply_text = "抱歉，我無法理解您的行程安排。"
            else:
                calendar_link = self.calendar_service.create_google_calendar_link(data)
                reply_text = f"好的，為您準備好日曆連結了！\n標題：{data.get('title')}\n時間：{data.get('start_time')}\n\n請點擊連結加入：\n{calendar_link}" if calendar_link else "抱歉，處理您的日曆請求時發生錯誤。"
            self._push_message(user_id, [TextMessage(text=reply_text)])
        self._execute_in_background(task)

    def _handle_translation(self, user_id, data):
        text_to_translate = data.get("text_to_translate")
        target_language = data.get("target_language")
        if not text_to_translate: return
        def task():
            user_message_for_translation = f"翻譯 {text_to_translate} 到 {target_language}"
            translated_text = self.text_service.translate_text(user_message_for_translation)
            self._push_message(user_id, [TextMessage(text=translated_text)])
        self._execute_in_background(task)

    def _handle_nearby_search(self, user_id, reply_token, data):
        query = data.get("query")
        if not query:
            self._reply_message(reply_token, [TextMessage(text="您好，請問想搜尋附近的什麼地點呢？")])
            return
        
        last_location = self.storage_service.get_user_last_location(user_id)
        if not last_location:
            self.storage_service.set_nearby_query(user_id, query)
            self._reply_message(reply_token, [TextMessage(text=f"好的，請分享您的位置，我將為您尋找附近的「{query}」。")])
            return

        def task():
            search_results = self.parsing_service.search_location(query=query, is_nearby=True, latitude=last_location['latitude'], longitude=last_location['longitude'])
            places = search_results.get('places') if search_results else None
            if not places:
                message = TextMessage(text=f"抱歉，在您附近找不到關於「{query}」的地點。")
            else:
                message = self._create_location_carousel(places, query)
            self._push_message(user_id, [message])
        self._execute_in_background(task)

    def _handle_help(self, reply_token):
        help_text = """
這是一個 AI 助理機器人，你可以跟我聊天，或使用以下指令：

**基本功能**
- **功能說明**: 顯示此訊息。
- **清除對話**: 清除我們的對話歷史，重新開始。

**工具**
- **畫 [描述]**: 我會根據你的描述畫一張圖。例如：`畫 一隻在月球上開心的貓`
- **待辦清單**: 顯示你目前的待辦事項。
- **新增待辦 [事項]**: 新增一項待辦事項。例如：`新增待辦 明天要買牛奶`
- **完成待辦 [編號或文字]**: 完成一項待辦事項。例如：`完成待辦 1` 或 `完成待辦 買牛奶`
- **傳送網址**: 我會幫你分析網頁內容並提供摘要。
- **傳送位置**: 我會記住你的位置，你可以問我附近有什麼。例如：`尋找附近的咖啡廳`

**AI 進階功能**
- **查詢天氣**: 例如：`台北今天天氣如何？` 或 `東京未來一週天氣預報`
- **查詢股價**: 例如：`台積電股價` 或 `查詢 AAPL`
- **查詢新聞**: `今天有什麼頭條新聞？`
- **新增日曆行程**: 例如：`幫我設定一個明天下午三點的會議，標題是專案討論`
- **翻譯**: 例如：`把你好翻譯成英文`

有任何問題，隨時都可以問我！
        """
        self._reply_message(reply_token, [TextMessage(text=help_text.strip())])

    def _handle_draw(self, user_id, reply_token, data):
        prompt = data.get("prompt")
        if not prompt:
            self._reply_message(reply_token, [TextMessage(text="請告訴我要畫什麼喔！")])
            return
        
        self._reply_message(reply_token, [TextMessage(text=f"好的，正在為您繪製「{prompt}」，請稍候...")])
        
        def task():
            translated_prompt = self.image_service.translate_prompt_for_drawing(prompt)
            image_bytes, status_msg = self.image_service.generate_image(translated_prompt)
            if image_bytes:
                image_url, upload_status = self.storage_service.upload_image(image_bytes)
                messages = [ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)] if image_url else [TextMessage(text=f"圖片上傳失敗: {upload_status}")]
            else:
                messages = [TextMessage(text=f"繪圖失敗: {status_msg}")]
            self._push_message(user_id, messages)
        self._execute_in_background(task)

    def _handle_clear_memory(self, user_id, reply_token):
        self.storage_service.clear_chat_history(user_id)
        self._reply_message(reply_token, [TextMessage(text="好的，我已經把我們之前的對話都忘光光了！")])

    def _handle_chat(self, user_id, user_message):
        def task():
            history = self.storage_service.get_chat_history(user_id)
            ai_response, updated_history = self.core_service.chat_with_history(user_message, history)
            self.storage_service.save_chat_history(user_id, updated_history)
            self._push_message(user_id, [TextMessage(text=ai_response)])
        self._execute_in_background(task)

    def _create_location_carousel(self, places: list, query: str) -> TemplateMessage:
        columns = []
        for place in places[:10]:
            title = place.get('displayName', {}).get('text', '地點資訊')[:40]
            address = place.get('formattedAddress', '地址未提供')[:60]
            maps_query = quote_plus(f"{title} {address}")
            maps_url = f"https://www.google.com/maps/search/?api=1&query={maps_query}"
            columns.append(CarouselColumn(title=title, text=address, actions=[URIAction(label='在地圖上查看', uri=maps_url)]))
        return TemplateMessage(alt_text=f"為您找到附近的「{query}」", template=CarouselTemplate(columns=columns))

    def _create_weather_forecast_carousel(self, data: dict) -> TemplateMessage:
        city_name = data.get("city", "未知城市")
        columns = []
        for daily_data in data.get("forecasts", []):
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
    
    def handle_postback(self, event):
        user_id = event.source.user_id
        reply_token = event.reply_token
        postback_data = event.postback.data
        logger.info(f"Received postback from user {user_id}: '{postback_data}'")
        self._reply_message(reply_token, [TextMessage(text=f"收到您的操作：{postback_data}")])
