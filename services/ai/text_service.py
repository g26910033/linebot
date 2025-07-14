"""
AI 文字處理服務模組
負責處理純文字的 AI 任務，如摘要、翻譯等。
"""
from utils.logger import get_logger
from .core import AICoreService

logger = get_logger(__name__)

class AITextService:
    """
    AI 文字處理服務類別，封裝與純文字相關的 AI 互動。
    """
    def __init__(self, core_service: AICoreService):
        self.core_service = core_service

    def _generate_content(self, prompt: str) -> str:
        """使用核心服務生成內容的輔助函式"""
        if not self.core_service.is_available():
            raise ConnectionError("AI Core Service is not available.")
        response = self.core_service.text_vision_model.generate_content(prompt)
        return self.core_service.clean_text(response.text)

    def summarize_text(self, text: str, max_length: int = 50000):
        """使用 AI 模型總結長篇文章"""
        if not self.core_service.is_available():
            return "AI 服務未啟用。"
        
        truncated_text = text[:max_length]

        prompt = f"""請你扮演一位專業的內容分析師。請用繁體中文，為以下文章產生一份約 200-300 字的精簡摘要，並在最後列出 3 個關鍵重點。
--- 文章開始 ---
{truncated_text}
--- 文章結束 ---"""
        try:
            return self._generate_content(prompt)
        except Exception as e:
            logger.error(f"Error during text summarization: {e}", exc_info=True)
            return "抱歉，摘要文章時發生錯誤。"

    def translate_text(self, user_message: str) -> str:
        """
        使用 AI 模型從自然語言中解析並翻譯文字。
        """
        if not self.core_service.is_available():
            return "翻譯服務未啟用。"

        prompt = f"""
        你是一個強大的翻譯助理。你的任務是從使用者的句子中，自動偵測出「要翻譯的內容」和「目標語言」。

        解析規則：
        1.  句子的任何部分都可能包含要翻譯的內容和目標語言。
        2.  如果使用者沒有明確指定目標語言，請預設翻譯成「繁體中文」。
        3.  你的回應必須是**純粹的翻譯結果**，絕對不能包含任何額外的解釋、前言或 markdown 符號。例如，如果使用者說「你好 翻譯英文」，你只能回傳 "Hello"。

        使用者輸入: "{user_message}"

        翻譯結果:
        """
        try:
            # 這裡不需要 clean_text，因為提示已經要求純文字
            response = self.core_service.text_vision_model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error during smart translation: {e}", exc_info=True)
            return "抱歉，翻譯時發生錯誤。"
