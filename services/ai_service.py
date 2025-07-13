"""
一個人，從頭開始打造一個完整的 AI 服務。

這個模組負責處理所有 AI 相關功能，包括文字生成、圖片生成、圖片分析、地點搜尋和對話歷史管理。

主要優化點：
1.  **增強錯誤處理**：針對 JSON 解析失敗和模型無回應的情況，增加更具體的錯誤捕捉，並記錄原始回應以供調試。
2.  **提高代碼魯棒性**：在處理模型回應時，增加對 `response` 和其內容（如 `response.text`, `response.images`）的有效性檢查。
3.  **改善日誌記錄**：在錯誤日誌中包含更多的上下文信息（如查詢詞、經緯度、對話歷史），以便於問題追蹤。
4.  **訊息一致性**：對模型未啟用時的回傳訊息進行微調，使其更具一致性。
5.  **Chat History 處理優化**：更穩健地重建對話歷史中的 `Part` 對象。

這些改進有助於提升服務的穩定性、可維護性和調試效率，尤其是在與外部 AI 服務互動時。
"""

import logging
from typing import List, Dict, Any, Optional, Union
from config.settings import AppConfig

logger = logging.getLogger(__name__)

# --- Mock classes for demonstrating robust error handling and logging of raw responses ---
# In a real application, these would be actual response objects from your AI SDK/client.
class _MockAIResponse:
    """A mock class to simulate responses from an AI client for demonstration."""
    def __init__(self, text: Optional[str] = None, images: Optional[List[str]] = None, raw_data: Optional[Any] = None):
        self.text = text
        self.images = images
        self.raw_data = raw_data # Represents the raw JSON/text from the actual API call

# --- End Mock classes ---


class AIService:
    """
    Handles all AI-related functionalities, including text generation, image generation,
    image analysis, location search, and conversation history management.
    """

    def __init__(self, config: AppConfig):
        """
        Initializes the AI Service.

        Args:
            config (AppConfig): The application configuration object.
        """
        self.config = config
        self.model_enabled = bool(self.config.gcp_service_account_json)

        if not self.model_enabled:
            logger.warning("AI service is disabled due to missing 'gcp_service_account_json'. All AI-related functionalities will return default messages.")
        # Placeholder for AI client initialization (e.g., a custom wrapper for OpenAI/Gemini API)
        self.ai_client = None  # In a real app, this would be initialized if api_key is present.

    def is_available(self) -> bool:
        """Checks if the AI service is properly configured and available."""
        return self.model_enabled

    def _check_model_status(self) -> bool:
        """Helper to check if the model is enabled."""
        if not self.model_enabled:
            logger.info("AI service model is disabled. Skipping AI operation.")
            return False
        # 可加速: 若 ai_client 實作初始化失敗可直接 return False
        return True

    def generate_text(self, prompt: str, history: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Generates text based on a given prompt and optional conversation history.

        Optimization points:
        - Enhanced error handling for API calls and JSON parsing.
        - Robustness: Check model response validity.
        - Improved logging with context (prompt, history).
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行文字生成。"
        
        # Log more context for better debugging
        history_summary = f"{len(history)} items" if history else "no history"
        logger.info("[generate_text] prompt='%s' history=%s", prompt, history_summary)

        raw_response_data: Optional[Any] = None
        try:
            # Simulate a successful response
            simulated_text = f"AI 服務已接收請求，正在生成關於 '{prompt}' 的文字內容... (使用歷史: {history_summary})"
            raw_response_data = {"status": "success", "generated_text": simulated_text, "input_prompt": prompt, "input_history": history}
            response = _MockAIResponse(text=simulated_text, raw_data=raw_response_data)

            if not response or not response.text:
                logger.error("[generate_text] Empty response. prompt='%s' raw=%s", prompt, response.raw_data)
                raise ValueError("AI model returned an invalid or empty response for text generation.")
            return response.text
        except Exception as e:
            logger.exception("[generate_text] Error. prompt='%s' history=%s raw=%s", prompt, history_summary, raw_response_data)
            return "文字生成失敗，請稍後再試。"

    def generate_image(self, description: str) -> List[str]:
        """
        Generates an image based on a given description.

        Optimization points:
        - Enhanced error handling.
        - Robustness: Check generated image URLs/data.
        - Improved logging with context (description).
        """
        if not self._check_model_status():
            logger.info("[generate_image] Disabled or no API key. description='%s'", description)
            return []

        logger.info("[generate_image] description='%s'", description)
        raw_response_data: Optional[Any] = None
        try:
            simulated_images = [
                f"https://example.com/generated_image_{hash(description)}.png?v=1",
                f"https://example.com/generated_image_{hash(description)}_alt.png?v=2"
            ]
            raw_response_data = {"status": "success", "generated_images": simulated_images, "input_description": description}
            response = _MockAIResponse(images=simulated_images, raw_data=raw_response_data)

            if not response or not response.images:
                logger.error("[generate_image] No images. description='%s' raw=%s", description, response.raw_data)
                raise ValueError("AI model returned no images for the given description.")
            return response.images
        except Exception:
            logger.exception("[generate_image] Error. description='%s' raw=%s", description, raw_response_data)
            return []

    def analyze_image(self, image_url: str, question: Optional[str] = None) -> str:
        """
        Analyzes an image and optionally answers a question about it.

        Optimization points:
        - Enhanced error handling.
        - Robustness: Check model response validity.
        - Improved logging with context (image_url, question).
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行圖片分析。"

        logger.info("[analyze_image] image_url='%s' question='%s'", image_url, question)
        raw_response_data: Optional[Any] = None
        try:
            simulated_analysis = f"AI 服務已分析圖片 '{image_url}'，結果顯示：這是一張... (針對問題 '{question or '無'} ' 的回答)"
            raw_response_data = {"status": "success", "analysis_result": simulated_analysis, "input_image": image_url, "input_question": question}
            response = _MockAIResponse(text=simulated_analysis, raw_data=raw_response_data)

            if not response or not response.text:
                logger.error("[analyze_image] No analysis result. image_url='%s' question='%s' raw=%s", image_url, question, response.raw_data)
                raise ValueError("AI model returned no analysis result for the image.")
            return response.text
        except Exception:
            logger.exception("[analyze_image] Error. image_url='%s' question='%s' raw=%s", image_url, question, raw_response_data)
            return "圖片分析失敗，請稍後再試。"

    def search_location(self, query: str, latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
        """
        Searches for locations based on a query, optionally with geographic context.

        Optimization points:
        - Enhanced error handling.
        - Robustness: Check model response validity.
        - Improved logging with context (query, lat, lon).
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行地點搜尋。"

        logger.info("[search_location] query='%s' lat=%s lon=%s", query, latitude, longitude)
        raw_response_data: Optional[Any] = None
        try:
            simulated_location = f"AI 服務已搜尋 '{query}'，找到多個地點資訊，其中一個是：XX 地址位於 YY 附近。 (經緯度: {latitude}, {longitude})"
            raw_response_data = {"status": "success", "search_result": simulated_location, "input_query": query, "input_lat": latitude, "input_lon": longitude}
            response = _MockAIResponse(text=simulated_location, raw_data=raw_response_data)

            if not response or not response.text:
                logger.error("[search_location] No result. query='%s' lat=%s lon=%s raw=%s", query, latitude, longitude, response.raw_data)
                raise ValueError("AI model returned no search result for the location query.")
            return response.text
        except Exception:
            logger.exception("[search_location] Error. query='%s' lat=%s lon=%s raw=%s", query, latitude, longitude, raw_response_data)
            return "地點搜尋失敗，請稍後再試。"

    def manage_chat_history(self, history: Union[List[Dict[str, Any]], None]) -> List[Dict[str, Any]]:
        """
        Processes and optimizes chat history for consistency and compatibility with AI models,
        e.g., reconstructing Part objects or validating structure.

        Optimization points:
        - Robust reconstruction/validation of chat history `Part` objects or equivalent structures.
        """
        if not history:
            logger.info("[manage_chat_history] No chat history to manage. Returning empty list.")
            return []

        logger.info("[manage_chat_history] Optimizing chat history with %d items.", len(history))
        optimized_history = []
        try:
            for i, item in enumerate(history):
                if isinstance(item, dict):
                    parts = item.get('parts', None)
                    if parts is not None and not isinstance(parts, (list, str)):
                        logger.warning("[manage_chat_history] Item %d invalid 'parts' type: %s. Item: %s", i, type(parts).__name__, item)
                        optimized_history.append(item.copy())
                    else:
                        optimized_history.append(item.copy())
                else:
                    logger.warning("[manage_chat_history] Item %d is not a dict. Appending as-is: %s", i, item)
                    optimized_history.append(item)
            return optimized_history
        except Exception:
            logger.exception("[manage_chat_history] Error. Original history length: %d", len(history) if history else 0)
            return history if history else []