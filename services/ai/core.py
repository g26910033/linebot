"""
AI 核心服務模組
負責與 Google Vertex AI 的基本互動，包含模型初始化和歷史對話。
加入配額管理和重試機制。
"""
import re
import time
import random
from vertexai.generative_models import GenerativeModel, Part, Content
from google.api_core import exceptions as gcp_exceptions
from config.settings import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class AICoreService:
    """
    AI 核心服務類別，封裝與 Vertex AI 的基本互動。
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.text_vision_model = None
        self._initialize_models()

    def _initialize_models(self):
        """根據設定初始化所有 AI 模型"""
        try:
            if self.config.text_model_name:
                self.text_vision_model = GenerativeModel(self.config.text_model_name)
                logger.info(
                    f"Text/Vision model '{self.config.text_model_name}' loaded for AICoreService.")
        except Exception as e:
            logger.error(
                f"AICoreService model initialization failed: {e}",
                exc_info=True)

    def is_available(self) -> bool:
        """檢查核心模型是否已成功初始化"""
        return self.text_vision_model is not None

    def clean_text(self, text: str) -> str:
        """移除 Gemini 回應中不必要的 Markdown 符號"""
        cleaned_text = re.sub(r'```json\n|```', '', text)
        cleaned_text = re.sub(r'[*#]', '', cleaned_text)
        return cleaned_text.strip()

    def _retry_with_backoff(self, func, max_retries=3, base_delay=1):
        """帶有指數退避的重試機制"""
        for attempt in range(max_retries):
            try:
                return func()
            except gcp_exceptions.ResourceExhausted as e:
                if attempt == max_retries - 1:
                    logger.error(f"配額耗盡，已重試 {max_retries} 次: {e}")
                    raise
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"配額限制，等待 {delay:.2f} 秒後重試 (第 {attempt + 1} 次)")
                time.sleep(delay)
            except gcp_exceptions.DeadlineExceeded as e:
                if attempt == max_retries - 1:
                    logger.error(f"請求超時，已重試 {max_retries} 次: {e}")
                    raise
                delay = base_delay * (2 ** attempt)
                logger.warning(f"請求超時，等待 {delay:.2f} 秒後重試 (第 {attempt + 1} 次)")
                time.sleep(delay)
            except Exception as e:
                logger.error(f"未預期的錯誤: {e}")
                raise

    def chat_with_history(self, user_message: str, history: list):
        """使用 ChatSession 進行有記憶的對話，加入重試機制"""
        if not self.is_available():
            return "AI 服務未啟用。", []

        reconstructed_history = []
        if history:
            for msg in history:
                role = msg.get("role")
                parts_data = msg.get("parts", [])
                parts = [Part.from_text(p.get("text", "")) for p in parts_data]
                if role and parts:
                    reconstructed_history.append(
                        Content(role=role, parts=parts))

        def _chat_request():
            chat_session = self.text_vision_model.start_chat(
                history=reconstructed_history)
            response = chat_session.send_message(user_message)
            cleaned_text = self.clean_text(response.text)
            
            updated_history = [
                {
                    "role": c.role,
                    "parts": [{"text": part.text} for part in c.parts]
                }
                for c in chat_session.history
            ]
            return cleaned_text, updated_history

        try:
            return self._retry_with_backoff(_chat_request)
        except gcp_exceptions.ResourceExhausted:
            return "抱歉，AI 服務目前使用量過高，請稍後再試。", history
        except gcp_exceptions.DeadlineExceeded:
            return "抱歉，AI 服務回應超時，請稍後再試。", history
        except Exception as e:
            logger.error(f"AI 對話時發生錯誤: {e}", exc_info=True)
            return "抱歉，AI 對話時發生錯誤，請稍後再試。", history
