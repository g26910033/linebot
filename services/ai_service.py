import logging
from typing import List, Dict, Any, Optional, Union, Tuple
from config.settings import AppConfig

logger = logging.getLogger(__name__)

# --- Mock classes for demonstrating robust error handling and logging of raw responses ---
# In a real application, these would be actual response objects from your AI SDK/client.

class _MockAIResponse:
    """
    模擬 AI 回應物件（僅示範用）。
    """
    def __init__(self, text: Optional[str] = None, images: Optional[List[str]] = None, raw_data: Optional[Any] = None) -> None:
        self.text: Optional[str] = text
        self.images: Optional[List[str]] = images
        self.raw_data: Optional[Any] = raw_data

# --- End Mock classes ---



class AIService:
    """
    AI 服務主類別，負責文字生成、圖片生成、圖片分析、地點搜尋、對話歷史管理。
    增強型別註解、日誌、錯誤處理與效能。
    """

    def __init__(self, config: AppConfig) -> None:
        """
        初始化 AI 服務。
        Args:
            config (AppConfig): 應用程式設定。
        """
        self.config: AppConfig = config
        self.model_enabled: bool = bool(self.config.gcp_service_account_json)
        if not self.model_enabled:
            logger.warning("AI service is disabled due to missing 'gcp_service_account_json'. All AI-related functionalities will return default messages.")
        self.ai_client: Optional[Any] = None  # 實際應用時初始化 AI client


    def is_available(self) -> bool:
        """
        檢查 AI 服務是否可用。
        Returns:
            bool: 可用為 True。
        """
        return self.model_enabled


    def _check_model_status(self) -> bool:
        """
        檢查模型是否啟用。
        Returns:
            bool: 啟用為 True。
        """
        if not self.model_enabled:
            logger.info("AI service model is disabled. Skipping AI operation.")
            return False
        return True


    def generate_text(self, prompt: str, history: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        文字生成。
        Args:
            prompt (str): 輸入提示。
            history (Optional[List[Dict[str, Any]]]): 對話歷史。
        Returns:
            str: 生成結果。
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行文字生成。"
        history_summary: str = f"{len(history)} items" if history else "no history"
        logger.info("[generate_text] prompt='%s' history=%s", prompt, history_summary)
        raw_response_data: Optional[Any] = None
        try:
            simulated_text: str = f"AI 服務已接收請求，正在生成關於 '{prompt}' 的文字內容... (使用歷史: {history_summary})"
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
        圖片生成。
        Args:
            description (str): 圖片描述。
        Returns:
            List[str]: 生成圖片網址清單。
        """
        if not self._check_model_status():
            logger.info("[generate_image] Disabled or no API key. description='%s'", description)
            return []
        logger.info("[generate_image] description='%s'", description)
        raw_response_data: Optional[Any] = None
        try:
            simulated_images: List[str] = [
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
        圖片分析。
        Args:
            image_url (str): 圖片網址。
            question (Optional[str]): 針對圖片的問題。
        Returns:
            str: 分析結果。
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行圖片分析。"
        logger.info("[analyze_image] image_url='%s' question='%s'", image_url, question)
        raw_response_data: Optional[Any] = None
        try:
            simulated_analysis: str = f"AI 服務已分析圖片 '{image_url}'，結果顯示：這是一張... (針對問題 '{question or '無'} ' 的回答)"
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
        地點搜尋。
        Args:
            query (str): 查詢字串。
            latitude (Optional[float]): 緯度。
            longitude (Optional[float]): 經度。
        Returns:
            str: 搜尋結果。
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法執行地點搜尋。"
        logger.info("[search_location] query='%s' lat=%s lon=%s", query, latitude, longitude)
        raw_response_data: Optional[Any] = None
        try:
            simulated_location: str = f"AI 服務已搜尋 '{query}'，找到多個地點資訊，其中一個是：XX 地址位於 YY 附近。 (經緯度: {latitude}, {longitude})"
            raw_response_data = {"status": "success", "search_result": simulated_location, "input_query": query, "input_lat": latitude, "input_lon": longitude}
            response = _MockAIResponse(text=simulated_location, raw_data=raw_response_data)
            if not response or not response.text:
                logger.error("[search_location] No result. query='%s' lat=%s lon=%s raw=%s", query, latitude, longitude, response.raw_data)
                raise ValueError("AI model returned no search result for the location query.")
            return response.text
        except Exception:
            logger.exception("[search_location] Error. query='%s' lat=%s lon=%s raw=%s", query, latitude, longitude, raw_response_data)
            return "地點搜尋失敗，請稍後再試。"


    def manage_chat_history(self, history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        對話歷史處理與優化。
        Args:
            history (Optional[List[Dict[str, Any]]]): 對話歷史。
        Returns:
            List[Dict[str, Any]]: 處理後的對話歷史。
        """
        if not history:
            logger.info("[manage_chat_history] No chat history to manage. Returning empty list.")
            return []
        logger.info("[manage_chat_history] Optimizing chat history with %d items.", len(history))
        optimized_history: List[Dict[str, Any]] = []
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


    def chat_with_history(self, message: str, history: Optional[List[Dict[str, Any]]] = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        依據訊息與對話歷史進行 AI 對話。
        
        Args:
            message (str): 使用者訊息。
            history (Optional[List[Dict[str, Any]]]): 對話歷史。

        Returns:
            Tuple[str, List[Dict[str, Any]]]: AI 回應與更新後的對話歷史。
        """
        if not self._check_model_status():
            return "AI 服務目前未啟用或設定不完整，無法進行對話。", history or []

        logger.info("[chat_with_history] message='%s' history_length=%d", 
                   message, len(history) if history else 0)

        try:
            # 初始化或清理歷史
            clean_history = self.manage_chat_history(history)
            
            # 加入使用者訊息
            updated_history = clean_history + [{"role": "user", "content": message}]
            
            # 生成回應
            response_text = self.generate_text(message, updated_history)
            
            # 加入 AI 回應到歷史
            updated_history.append({"role": "assistant", "content": response_text})
            
            return response_text, updated_history
            
        except Exception as e:
            logger.exception("[chat_with_history] Error processing chat. message='%s'", message)
            return "對話處理發生錯誤，請稍後再試。", history or []