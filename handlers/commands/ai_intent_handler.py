"""
AI 意圖處理器
"""
import threading
from datetime import datetime
from linebot.v3.messaging import (
    MessagingApi, TextMessage, PushMessageRequest, FlexMessage,
    FlexContainer)
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

    def handle(self, user_id: str, user_message: str) -> bool:
        """
        使用 AI 判斷使用者意圖，並路由到對應的處理器。
        """
        intent_data = self.parsing_service.parse_intent_from_text(user_message)
        intent = intent_data.get("intent")
        data = intent_data.get("data")

        if not intent or intent == "general_chat":
            return False

        logger.info(f"AI Intent detected: {intent} with data: {data}")

        handler_map = {
            "weather": self._handle_weather,
            "stock": self._handle_stock,
            "news": self._handle_news,
            "calendar": self._handle_calendar,
            "translation": self._handle_translation,
            "nearby_search": self._handle_nearby_search,
        }

        handler = handler_map.get(intent)
        if handler:
            if intent in ["weather", "stock", "calendar", "translation", "nearby_search"]:
                handler(user_id, data)
            else:
                handler(user_id)
            return True

        return False

    def _handle_weather(self, user_id, data):
        city = data.get("city")
        if not city: return
        query_type = data.get("type", "current")

        def task():
            if query_type == "forecast":
                forecast_data = self.weather_service.get_weather_forecast(city)
                message = TextMessage(text=forecast_data) if isinstance(forecast_data, str) else FlexMessage(alt_text=f"{city} 的天氣預報", contents=self._create_weather_forecast_carousel(forecast_data))
            else:
                result = self.weather_service.get_current_weather(city)
                message = TextMessage(text=result)
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[message]))
        threading.Thread(target=task).start()

    def _handle_stock(self, user_id, data):
        symbol = data.get("symbol")
        if not symbol: return
        def task():
            result = self.stock_service.get_stock_quote(symbol)
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=result)]))
        threading.Thread(target=task).start()

    def _handle_news(self, user_id):
        def task():
            formatted_news = self.news_service.get_top_headlines()
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=formatted_news)]))
        threading.Thread(target=task).start()

    def _handle_calendar(self, user_id, data):
        def task():
            if not data or not data.get('title'):
                reply_text = "抱歉，我無法理解您的行程安排，可以說得更清楚一點嗎？"
            else:
                calendar_link = self.calendar_service.create_google_calendar_link(data)
                reply_text = f"好的，我為您準備好日曆連結了！\n\n標題：{data.get('title')}\n時間：{data.get('start_time')}\n\n請點擊下方連結將它加入您的 Google 日曆：\n{calendar_link}" if calendar_link else "抱歉，處理您的日曆請求時發生錯誤。"
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=reply_text)]))
        threading.Thread(target=task).start()

    def _handle_translation(self, user_id, data):
        text_to_translate = data.get("text_to_translate")
        target_language = data.get("target_language")
        if not text_to_translate: return
        def task():
            user_message_for_translation = f"翻譯 {text_to_translate} 到 {target_language}"
            translated_text = self.text_service.translate_text(user_message_for_translation)
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=translated_text)]))
        threading.Thread(target=task).start()

    def _handle_nearby_search(self, user_id, data):
        query = data.get("query")
        if not query: return
        def task():
            last_location = self.storage_service.get_user_last_location(user_id)
            if not last_location:
                self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="請先分享您的位置，我才能幫您尋找附近的地點喔！")]))
                return

            search_results = self.parsing_service.search_location(query=query, is_nearby=True, latitude=last_location['latitude'], longitude=last_location['longitude'])
            places = search_results.get('places') if search_results else None
            if not places:
                message = TextMessage(text=f"抱歉，在您附近找不到關於「{query}」的地點。")
            else:
                carousel = self._create_location_carousel(places)
                message = FlexMessage(alt_text=f"為您找到附近的「{query}」", contents=carousel)
            self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[message]))
        threading.Thread(target=task).start()

    def _create_location_carousel(self, places: list) -> FlexContainer:
        bubbles = []
        for place in places:
            display_name = place.get('displayName', {}).get('text', '無名稱')
            address = place.get('formattedAddress', '無地址')
            maps_url = f"https://www.google.com/maps/search/?api=1&query={display_name.replace(' ', '+')}+{address.replace(' ', '+')}"
            bubble = {"type": "bubble", "header": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": "📍 地點資訊", "color": "#ffffff", "weight": "bold"}], "backgroundColor": "#007BFF"}, "body": {"type": "box", "layout": "vertical", "spacing": "md", "contents": [{"type": "text", "text": display_name, "weight": "bold", "size": "xl", "wrap": True}, {"type": "text", "text": address, "wrap": True, "size": "sm", "color": "#666666"}]}, "footer": {"type": "box", "layout": "vertical", "contents": [{"type": "button", "action": {"type": "uri", "label": "在 Google Maps 上查看", "uri": maps_url}, "style": "primary", "height": "sm"}]}}
            bubbles.append(FlexContainer.from_dict(bubble))
        return FlexContainer(type="carousel", contents=bubbles)

    def _create_weather_forecast_carousel(self, data: dict) -> FlexContainer:
        bubbles = []
        for forecast in data.get('forecasts', []):
            bubble = {"type": "bubble", "body": {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": datetime.fromtimestamp(forecast['dt']).strftime('%m/%d (%a)'), "weight": "bold", "size": "xl", "align": "center"}, {"type": "image", "url": f"https://openweathermap.org/img/wn/{forecast['icon']}@2x.png", "size": "md", "aspectMode": "fit"}, {"type": "box", "layout": "vertical", "contents": [{"type": "text", "text": f"{forecast['description']}", "size": "lg", "align": "center", "wrap": True}, {"type": "text", "text": f"{round(forecast['temp_min'])}°C - {round(forecast['temp_max'])}°C", "size": "md", "align": "center", "color": "#666666"}]}]}}
            bubbles.append(FlexContainer.from_dict(bubble))
        return FlexContainer(type="carousel", contents=bubbles)
