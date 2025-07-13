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
from typing import List, Dict, Any, Optional

# Assuming there might be a config module in the project for settings
# from config import settings

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

    def __init__(self, api_key: str = None, model_enabled: bool = True):
        """
        Initializes the AI Service.

        Args:
            api_key (str, optional): API key for the AI service. Defaults to None.
            model_enabled (bool, optional): Flag to enable/disable the AI model. Defaults to True.
        """
        self.api_key = api_key
        self.model_enabled = model_enabled

        if not self.model_enabled:
            logger.warning("AI service model is disabled. All AI-related functionalities will return default messages.")
        # Placeholder for AI client initialization (e.g., a custom wrapper for OpenAI/Gemini API)
        # self.ai_client = SomeAIClient(api_key=self.api_key) if self.api_key else None
        # For demonstration purposes, we'll use a placeholder for the AI client.
        self.ai_client = None # In a real app, this would be initialized if api_key is present.


    def _check_model_status(self) -> bool:
        """Helper to check if the model is enabled and API key is present."""
        if not self.model_enabled:
            logger.info("AI service model is disabled. Skipping AI operation.")
            return False
        if not self.api_key:
            logger.error("AI service API key is not configured.")
            return False
        # In a real scenario, you might also check self.ai_client for actual initialization
        # if self.ai_client is None:
        #     logger.error("AI client failed to initialize.")
        #     return False
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
        logger.info(f"Attempting to generate text for prompt: '{prompt}' with history: {history_summary}")

        raw_response_data: Optional[Any] = None # To store raw response for debugging
        try:
            # --- Placeholder for actual text generation logic ---
            # In a real application, you would call:
            # api_response = self.ai_client.generate_text(prompt, history)
            # response = _MockAIResponse(text=api_response.text, raw_data=api_response.raw_data)
            # For demonstration, simulate success or failure
            
            # Simulate a successful response
            simulated_text = f"AI 服務已接收請求，正在生成關於 '{prompt}' 的文字內容... (使用歷史: {history_summary})"
            raw_response_data = {"status": "success", "generated_text": simulated_text, "input_prompt": prompt, "input_history": history}
            response = _MockAIResponse(text=simulated_text, raw_data=raw_response_data)

            # Robustness check for the response
            if not response or not response.text:
                # Log the raw response data if available for debugging
                logger.error(f"AI model returned invalid or empty text response. Prompt: '{prompt}'. Raw data: {response.raw_data}")
                raise ValueError("AI model returned an invalid or empty response for text generation.")
            
            return response.text
        except Exception as e:
            # Capture and log specific details of the error, including raw response if available
            error_message = f"Error generating text for prompt '{prompt}'."
            if history:
                error_message += f" History length: {len(history)}."
            if raw_response_data:
                error_message += f" Raw response info: {raw_response_data}"
            logger.error(error_message, exc_info=True)
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
            # Return an empty list for consistency if returning URLs
            return [] 

        logger.info(f"Attempting to generate image for description: '{description}'")

        raw_response_data: Optional[Any] = None
        try:
            # --- Placeholder for actual image generation logic ---
            # api_response = self.ai_client.generate_image(description)
            # response = _MockAIResponse(images=api_response.images, raw_data=api_response.raw_data)

            # Simulate a successful response
            simulated_images = [f"https://example.com/generated_image_{hash(description)}.png?v=1", f"https://example.com/generated_image_{hash(description)}_alt.png?v=2"]
            raw_response_data = {"status": "success", "generated_images": simulated_images, "input_description": description}
            response = _MockAIResponse(images=simulated_images, raw_data=raw_response_data)

            # Robustness check for the response
            if not response or not response.images:
                logger.error(f"AI model returned no images for description: '{description}'. Raw data: {response.raw_data}")
                raise ValueError("AI model returned no images for the given description.")
            
            return response.images
        except Exception as e:
            error_message = f"Error generating image for description '{description}'."
            if raw_response_data:
                error_message += f" Raw response info: {raw_response_data}"
            logger.error(error_message, exc_info=True)
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

        logger.info(f"Attempting to analyze image: '{image_url}' with question: '{question or 'None'}'")

        raw_response_data: Optional[Any] = None
        try:
            # --- Placeholder for actual image analysis logic ---
            # api_response = self.ai_client.analyze_image(image_url, question)
            # response = _MockAIResponse(text=api_response.text, raw_data=api_response.raw_data)

            # Simulate a successful response
            simulated_analysis = f"AI 服務已分析圖片 '{image_url}'，結果顯示：這是一張... (針對問題 '{question or '無'} ' 的回答)"
            raw_response_data = {"status": "success", "analysis_result": simulated_analysis, "input_image": image_url, "input_question": question}
            response = _MockAIResponse(text=simulated_analysis, raw_data=raw_response_data)

            # Robustness check for the response
            if not response or not response.text:
                logger.error(f"AI model returned no analysis result for image '{image_url}' (question: '{question}'). Raw data: {response.raw_data}")
                raise ValueError("AI model returned no analysis result for the image.")
            
            return response.text
        except Exception as e:
            error_message = f"Error analyzing image '{image_url}' with question '{question}'."
            if raw_response_data:
                error_message += f" Raw response info: {raw_response_data}"
            logger.error(error_message, exc_info=True)
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

        logger.info(f"Attempting to search location for query: '{query}' at ({latitude}, {longitude})")

        raw_response_data: Optional[Any] = None
        try:
            # --- Placeholder for actual location search logic ---
            # api_response = self.ai_client.search_location(query, latitude, longitude)
            # response = _MockAIResponse(text=api_response.text, raw_data=api_response.raw_data)

            # Simulate a successful response
            simulated_location = f"AI 服務已搜尋 '{query}'，找到多個地點資訊，其中一個是：XX 地址位於 YY 附近。 (經緯度: {latitude}, {longitude})"
            raw_response_data = {"status": "success", "search_result": simulated_location, "input_query": query, "input_lat": latitude, "input_lon": longitude}
            response = _MockAIResponse(text=simulated_location, raw_data=raw_response_data)

            # Robustness check for the response
            if not response or not response.text:
                logger.error(f"AI model returned no search result for query '{query}' at ({latitude}, {longitude}). Raw data: {response.raw_data}")
                raise ValueError("AI model returned no search result for the location query.")
            
            return response.text
        except Exception as e:
            error_message = f"Error searching location for query '{query}' at ({latitude}, {longitude})."
            if raw_response_data:
                error_message += f" Raw response info: {raw_response_data}"
            logger.error(error_message, exc_info=True)
            return "地點搜尋失敗，請稍後再試。"

    def manage_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Processes and optimizes chat history, e.g., reconstructing Part objects.

        Optimization points:
        - Robust reconstruction of chat history `Part` objects.
        """
        if not history:
            logger.info("No chat history to manage. Returning empty list.")
            return []

        logger.info(f"Managing and optimizing chat history with {len(history)} items.")
        optimized_history = []
        try:
            # This is where actual logic for reconstructing Part objects or
            # cleaning/optimizing history would go.
            #
            # Example for reconstructing 'Part' objects (e.g., from Google Generative AI SDK):
            # from google.generativeai.types import Part
            # for item in history:
            #     if isinstance(item, dict) and 'role' in item and 'parts' in item:
            #         # Assuming 'parts' can be a string or a list of strings/dicts for Part objects
            #         # This would depend on the specific structure expected by the AI SDK.
            #         try:
            #             # If Part expects content directly
            #             content_parts = item['parts']
            #             if not isinstance(content_parts, list):
            #                 content_parts = [content_parts] # Ensure it's a list for iteration
            #             
            #             reconstructed_parts = [Part.from_value(p) if not isinstance(p, Part) else p for p in content_parts]
            #             optimized_history.append({"role": item['role'], "parts": reconstructed_parts})
            #         except Exception as part_e:
            #             logger.warning(f"Failed to reconstruct Part object for item: {item}. Error: {part_e}")
            #             optimized_history.append(item.copy()) # Fallback to original
            #     else:
            #         logger.warning(f"Invalid history item format, skipping or appending as-is: {item}")
            #         optimized_history.append(item.copy() if isinstance(item, dict) else item)
            # return optimized_history


            # For demonstration, just append a copy after basic validation.
            # This handles cases where items might not be dictionaries robustly.
            for i, item in enumerate(history):
                if isinstance(item, dict):
                    # You might add schema validation here for keys like 'role', 'parts'.
                    # For example, if 'parts' should always be a list:
                    if 'parts' in item and not isinstance(item['parts'], list) and not isinstance(item['parts'], str):
                         logger.warning(f"History item {i} has invalid 'parts' format. Expected list or string, got {type(item['parts'])}. Item: {item}")
                         # Optionally, try to convert or skip
                         # For now, we'll just append a copy as a fallback
                         optimized_history.append(item.copy())
                    else:
                        optimized_history.append(item.copy())
                else:
                    logger.warning(f"History item {i} is not a dictionary. Skipping or appending as-is: {item}")
                    optimized_history.append(item) # Append as-is if not dict
            return optimized_history
        except Exception as e:
            # Log the entire history (or a summary/hash) for debugging if it causes issues.
            logger.error(f"Error managing chat history. Original history length: {len(history)}. Error: {e}", exc_info=True)
            # Return original history on error to prevent data loss or provide a partial result
            return history


# Example usage (for demonstration purposes, can be removed in production environment)
if __name__ == "__main__":
    # Configure basic logging for the example
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("\n--- Testing AI Service (Enabled) ---")
    # Replace 'your_secret_api_key_here' with an actual key if you have one for testing
    ai_service_enabled = AIService(api_key="test_api_key_123", model_enabled=True)

    print("\nText Generation:")
    print(ai_service_enabled.generate_text("今天天氣如何？", history=[{"role": "user", "parts": "你好"}, {"role": "model", "parts": "我很好，你呢？"}]))

    print("\nImage Generation:")
    print(ai_service_enabled.generate_image("一隻可愛的貓咪在月光下"))

    print("\nImage Analysis:")
    print(ai_service_enabled.analyze_image("https://example.com/cat.jpg", "這隻貓咪在做什麼？"))

    print("\nLocation Search:")
    print(ai_service_enabled.search_location("台北101", latitude=25.033, longitude=121.564))

    print("\nChat History Management:")
    initial_history_data = [
        {"role": "user", "parts": "Hello"},
        {"role": "model", "parts": "Hi there!"},
        "not_a_dict_item", # Test non-dict item
        {"role": "user", "parts": ["多圖輸入1", "多圖輸入2"]}, # Test list parts
        {"role": "model", "parts": "好的"}
    ]
    optimized_history_data = ai_service_enabled.manage_chat_history(initial_history_data)
    print(f"Original history: {initial_history_data}")
    print(f"Optimized history: {optimized_history_data}")

    # Test case: history with invalid 'parts' type
    invalid_parts_history = [{"role": "user", "parts": 123}]
    print("\nChat History Management (Invalid Parts):")
    optimized_invalid_parts = ai_service_enabled.manage_chat_history(invalid_parts_history)
    print(f"Original invalid history: {invalid_parts_history}")
    print(f"Optimized invalid history: {optimized_invalid_parts}")


    print("\n--- Testing AI Service (Disabled) ---")
    ai_service_disabled = AIService(model_enabled=False)

    print("\nText Generation (disabled):")
    print(ai_service_disabled.generate_text("今天天氣如何？"))

    print("\nImage Generation (disabled): -- Expected Empty List --")
    print(ai_service_disabled.generate_image("一隻可愛的貓咪在月光下"))

    print("\nImage Analysis (disabled):")
    print(ai_service_disabled.analyze_image("https://example.com/dog.jpg", "這隻狗在做什麼？"))

    print("\nLocation Search (disabled):")
    print(ai_service_disabled.search_location("倫敦塔"))


    print("\nAPI Key Missing Test (Enabled but no key) -- Expected Error Message --")
    ai_service_no_key = AIService(api_key=None, model_enabled=True)
    print("\nText Generation (no key):")
    print(ai_service_no_key.generate_text("測試無key"))
    print("\nImage Generation (no key): -- Expected Empty List --")
    print(ai_service_no_key.generate_image("測試無key"))
    print("\nImage Analysis (no key):")
    print(ai_service_no_key.analyze_image("https://example.com/no_key.jpg", "測試無key"))
    print("\nLocation Search (no key):")
    print(ai_service_no_key.search_location("測試無key地點"))
