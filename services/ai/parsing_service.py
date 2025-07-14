"""
AI 意圖解析服務模組
負責從自然語言文本中解析出結構化的資訊。
"""
import json
import pytz
from datetime import datetime
from config.settings import AppConfig
from utils.logger import get_logger
from .core import AICoreService

logger = get_logger(__name__)

class AIParsingService:
    """
    AI 意圖解析服務，專門處理從文本中提取結構化數據的任務。
    """
    def __init__(self, config: AppConfig, core_service: AICoreService):
        self.config = config
        self.core_service = core_service

    def _generate_content(self, prompt: str) -> str:
        """使用核心服務生成內容的輔助函式"""
        if not self.core_service.is_available():
            raise ConnectionError("AI Core Service is not available.")
        response = self.core_service.text_vision_model.generate_content(prompt)
        return self.core_service.clean_text(response.text)

    def search_location(self, query: str, is_nearby=False, latitude=None, longitude=None):
        """搜尋地點或周邊"""
        json_structure_prompt = f"""
        請以 JSON 格式回傳最多 {self.config.max_search_results} 個地點。
        JSON 格式必須是：
        {{
          "places": [
            {{
              "displayName": {{ "text": "地點的完整名稱" }},
              "formattedAddress": "地點的完整地址"
            }}
          ]
        }}
        如果找不到任何地點，請回傳：
        {{ "places": [] }}
        """
        if is_nearby:
            prompt = f"""你是一個專業的在地嚮導。根據以下資訊，找出相關地點。
            使用者位置：緯度 {latitude}, 經度 {longitude}
            查詢關鍵字: {query}
            {json_structure_prompt}
            """
        else:
            prompt = f"""你是一個專業的地點搜尋助理。根據以下資訊，找出相關地點。
            使用者查詢的關鍵字是：「{query}」
            {json_structure_prompt}
            """
        try:
            cleaned_response = self._generate_content(prompt)
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"Location search failed for query '{query}' due to JSONDecodeError: {e}. Raw AI response: '{cleaned_response}'", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during location search for query '{query}': {e}", exc_info=True)
            return None

    def parse_event_from_text(self, text: str) -> dict | None:
        """從自然語言中解析出事件的標題、開始時間和結束時間。"""
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
        prompt = f"""
        你是一個聰明的行程安排助理。請從以下使用者輸入的文字中，解析出日曆事件的資訊。
        目前的台灣時間是：{current_time}。
        你的任務是提取三項資訊：
        1.  `title`: 事件的標題。
        2.  `start_time`: 事件的開始時間，格式為 `YYYY-MM-DDTHH:MM:SS`。
        3.  `end_time`: 事件的結束時間，格式為 `YYYY-MM-DDTHH:MM:SS`。
        解析規則：
        -   如果使用者沒有提到具體的結束時間，請將結束時間設定為開始時間的一小時後。
        -   如果使用者只提到日期而沒有時間（例如「明天」），請將開始時間設定為該日期的早上 9 點。
        -   能夠理解相對時間，例如「明天」、「後天」、「下週三」、「三小時後」。
        -   如果無法解析出有效的時間，`start_time` 和 `end_time` 應為 null。
        -   你的回應必須是純粹的 JSON 格式，不包含任何其他文字或 markdown 符號。
        使用者輸入: "{text}"
        JSON 輸出:
        """
        try:
            cleaned_response = self._generate_content(prompt)
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"Error parsing event from text: {e}", exc_info=True)
            return None

    def parse_stock_symbol_from_text(self, text: str) -> str | None:
        """從自然語言中解析出股票代碼。"""
        prompt = f"""
        你是一個金融領域的專家，專門從句子中提取股票代碼。
        你的任務是分析以下使用者輸入的文字，並找出其中提到的公司或股票代碼。
        解析規則：
        - 如果句子中包含明確的股票代碼（例如 '2330', 'TSLA', 'AAPL'），直接回傳該代碼。
        - 如果句子中包含公司名稱（例如「台積電」、「蘋果公司」、「特斯拉」），請回傳該公司最廣為人知的股票代碼。
        - 如果句子與查詢股價無關，或找不到任何公司/股票代碼，請回傳 "null"。
        - 你的回應必須是純粹的股票代碼或 "null"，絕對不能包含任何其他文字或 markdown 符號。
        一些常見公司的對應：
        - 台積電: 2330.TW
        - 聯發科: 2454.TW
        - 鴻海: 2317.TW
        - 蘋果: AAPL
        - Google: GOOGL
        - 特斯拉: TSLA
        - 輝達 (Nvidia): NVDA
        使用者輸入: "{text}"
        股票代碼:
        """
        try:
            cleaned_response = self._generate_content(prompt)
            if cleaned_response.lower() == 'null':
                return None
            return cleaned_response
        except Exception as e:
            logger.error(f"Error parsing stock symbol from text: {e}", exc_info=True)
            return None

    def parse_weather_query_from_text(self, text: str) -> dict | None:
        """從自然語言中解析出天氣查詢的城市和類型（即時或預報）。"""
        prompt = f"""
        你是一個天氣查詢助理。請從使用者的句子中，解析出「城市」和「查詢類型」。
        解析規則：
        1.  **城市 (city)**: 使用者想要查詢的地點。如果沒有提到具體城市，請回傳 null。
        2.  **查詢類型 (type)**:
            - 如果句子中包含「預報」、「未來」、「明天」、「後天」、「這週」等關鍵字，請設為 "forecast"。
            - 否則，一律設為 "current"。
        3.  你的回應必須是純粹的 JSON 格式，不包含任何其他文字或 markdown 符號。
            如果無法解析出城市，請回傳 `{{ "city": null, "type": "current" }}`。
        使用者輸入: "{text}"
        JSON 輸出:
        """
        try:
            cleaned_response = self._generate_content(prompt)
            data = json.loads(cleaned_response)
            if data.get("city"):
                return data
            return None
        except Exception as e:
            logger.error(f"Error parsing weather query from text: {e}", exc_info=True)
            return None

    def parse_currency_conversion_query(self, text: str) -> dict | None:
        """從自然語言中解析出貨幣換算的數值、來源貨幣和目標貨幣。"""
        prompt = f"""
        你是一個貨幣換算專家。請從使用者的句子中，解析出「數值」、「來源貨幣」和「目標貨幣」。
        解析規則：
        -   **數值 (value)**: 要換算的金額。
        -   **來源貨幣 (from_currency)**: 原始貨幣的口語化名稱或代碼。
        -   **目標貨幣 (to_currency)**: 目標貨幣的口語化名稱或代碼。
        -   如果無法解析出所有必要資訊，請回傳 `{{ "value": null, "from_currency": null, "to_currency": null }}`。
        -   你的回應必須是純粹的 JSON 格式，不包含任何其他文字或 markdown 符號。
        常見貨幣名稱與其 ISO 代碼的對應（請優先使用 ISO 代碼）：
        -   台幣: TWD
        -   新台幣: TWD
        -   美元: USD
        -   美金: USD
        -   日圓: JPY
        -   日幣: JPY
        -   歐元: EUR
        -   英鎊: GBP
        -   人民幣: CNY
        -   韓元: KRW
        -   港幣: HKD
        -   加幣: CAD
        -   澳幣: AUD
        使用者輸入: "{text}"
        JSON 輸出:
        """
        try:
            cleaned_response = self._generate_content(prompt)
            data = json.loads(cleaned_response)
            if data.get("value") and data.get("from_currency") and data.get("to_currency"):
                return data
            return None
        except Exception as e:
            logger.error(f"Error parsing currency conversion query from text: {e}", exc_info=True)
            return None
