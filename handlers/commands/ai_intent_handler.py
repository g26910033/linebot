"""
AI 意圖處理器
"""
import threading
from linebot.v3.messaging import (
    MessagingApi, TextMessage, PushMessageRequest)
from services.ai.parsing_service import AIParsingService
from services.storage_service import StorageService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.stock_service import StockService
from services.calendar_service import CalendarService
from services.ai.text_service import AITextService
from utils.logger import get_logger

logger = get_logger(__name__)


class AIIntentHandler:
    """處理由 AI 解析出的意圖。"""

    def __init__(
            self,
            parsing_service: AIParsingService,
            text_service: AITextService,
            storage_service: StorageService,
            weather_service: WeatherService,
            news_service: NewsService,
            stock_service: StockService,
            calendar_service: CalendarService,
            line_bot_api: MessagingApi):
        self.parsing_service = parsing_service
        self.text_service = text_service
        self.storage_service = storage_service
        self.weather_service = weather_service
        self.news_service = news_service
        self.stock_service = stock_service
        self.calendar_service = calendar_service
        self.line_bot_api = line_bot_api

    def handle(self, user_id: str, user_message: str):
        """根據使用者訊息，解析意圖並執行對應操作。"""

        # 天氣查詢
        weather_query = self.parsing_service.parse_weather_query_from_text(
            user_message)
        if weather_query and weather_query.get("city"):
            self._handle_weather(user_id, weather_query)
            return True

        # 股票查詢
        symbol = self.parsing_service.parse_stock_symbol_from_text(
            user_message)
        if symbol:
            self._handle_stock(user_id, symbol)
            return True

        # 新聞查詢
        if any(keyword in user_message.lower() for keyword in ["新聞", "頭條"]):
            self._handle_news(user_id)
            return True

        # 日曆查詢
        if any(keyword in user_message.lower()
               for keyword in ["提醒我", "新增日曆", "新增行程", "的日曆"]):
            self._handle_calendar(user_id, user_message)
            return True

        # 翻譯查詢
        if any(keyword in user_message.lower() for keyword in ["翻譯", "翻成"]):
            self._handle_translation(user_id, user_message)
            return True

        # 地點搜尋 (新增的邏輯)
        if any(keyword in user_message.lower() for keyword in ["附近", "找", "搜尋"]):
            self._handle_nearby_search(user_id, user_message)
            return True

        return False  # 未匹配到任何 AI 意圖

    def _handle_weather(self, user_id, weather_query):
        city = weather_query["city"]
        query_type = weather_query.get("type", "current")

        def task():
            if query_type == "forecast":
                result = self.weather_service.get_weather_forecast(city)
                # 這部分需要重構 _create_weather_forecast_carousel
                message = TextMessage(text=str(result))  # 簡化處理
            else:
                result = self.weather_service.get_current_weather(city)
                message = TextMessage(text=result)
            push_request = PushMessageRequest(to=user_id, messages=[message])
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()

    def _handle_stock(self, user_id, symbol):
        def task():
            result = self.stock_service.get_stock_quote(symbol)
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=result)]
            )
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()

    def _handle_news(self, user_id):
        def task():
            # news_service.get_top_headlines() 已經回傳格式化好的字串
            formatted_news = self.news_service.get_top_headlines()
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=formatted_news)]
            )
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()

    def _handle_calendar(self, user_id, user_message):
        def task():
            event_data = self.parsing_service.parse_event_from_text(
                user_message)
            if not event_data or not event_data.get('title'):
                reply_text = "抱歉，我無法理解您的行程安排，可以說得更清楚一點嗎？"
            else:
                calendar_link = self.calendar_service.create_google_calendar_link(
                    event_data)
                if not calendar_link:
                    reply_text = "抱歉，處理您的日曆請求時發生錯誤。"
                else:
                    reply_text = (
                        f"好的，我為您準備好日曆連結了！\n\n"
                        f"標題：{event_data.get('title')}\n"
                        f"時間：{event_data.get('start_time')}\n\n"
                        "請點擊下方連結將它加入您的 Google 日曆：\n"
                        f"{calendar_link}")
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()

    def _handle_translation(self, user_id, user_message):
        def task():
            translated_text = self.text_service.translate_text(user_message)
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=translated_text)]
            )
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()

    def _handle_nearby_search(self, user_id, user_message):
        """處理附近地點搜尋的意圖。"""
        def task():
            last_location = self.storage_service.get_user_last_location(user_id)
            if not last_location:
                reply_text = "請先分享您的位置，我才能幫您尋找附近的地點喔！"
                push_request = PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=reply_text)]
                )
                self.line_bot_api.push_message(push_request)
                return

            # 這裡未來可以串接真正的 Google Maps API
            # 目前先回覆一則確認訊息
            reply_text = f"收到您的搜尋指令：「{user_message}」。\n我將在您分享的位置：(lat: {last_location['lat']}, lon: {last_location['lon']}) 附近尋找。"
            push_request = PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
            self.line_bot_api.push_message(push_request)
        threading.Thread(target=task).start()
