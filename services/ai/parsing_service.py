"""
AI 意圖解析服務模組
負責從自然語言文本中解析出結構化的資訊。
"""
import json
import pytz
from datetime import datetime
from config.settings import AppConfig
from utils.logger import get_logger
from vertexai.generative_models import Part
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
        # 將字串 prompt 轉換為 Vertex AI SDK 期望的格式
        response = self.core_service.text_vision_model.generate_content(
            [Part.from_text(prompt)]
        )
        return self.core_service.clean_text(response.text)

    def parse_intent_from_text(self, text: str) -> dict:
        """從自然語言中解析出意圖和相關數據。"""
        tw_tz = pytz.timezone('Asia/Taipei')
        current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
        prompt = f"""
        Analyze the user input and return a single JSON object with "intent" and "data".
        Possible intents: "weather", "stock", "news", "calendar", "translation", "nearby_search", "general_chat".
        - weather: requires "city" and "type" (current/forecast).
        - stock: requires "symbol".
        - news: data is empty.
        - calendar: requires "title", "start_time", "end_time".
        - translation: requires "text_to_translate", "target_language".
        - nearby_search: requires "query".
        - general_chat: for anything else.
        Current time: {current_time}.
        User input: "{text}"
        JSON output:
        """
        try:
            cleaned_response = self._generate_content(prompt)
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"Error parsing intent from text: {e}", exc_info=True)
            # 修正語法錯誤，{{}} -> {}
            return {"intent": "general_chat", "data": {}}

    def search_location(
            self,
            query: str,
            is_nearby=False,
            latitude=None,
            longitude=None):
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
            logger.error(
                f"Location search failed for query '{query}' due to "
                f"JSONDecodeError: {e}. Raw AI response: '{cleaned_response}'",
                exc_info=True)
            return None
        except Exception as e:
            logger.error(
                "An unexpected error occurred during location search for "
                f"query '{query}': {e}",
                exc_info=True)
            return None
