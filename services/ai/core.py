"""
AI 核心服務模組
負責與 Google Vertex AI 的基本互動，包含模型初始化和歷史對話。
"""
import re
from vertexai.generative_models import GenerativeModel, Part, Content
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
                # 確保使用完整的模型路徑，包含專案 ID
                model_path = (
                    f"projects/{self.config.gcp_project_id}/locations/"
                    f"{self.config.gcp_location}/publishers/google/models/"
                    f"{self.config.text_model_name}"
                )
                self.text_vision_model = GenerativeModel(model_path)
                logger.info(
                    f"Text/Vision model '{model_path}' loaded for AICoreService.")
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

    def chat_with_history(self, user_message: str, history: list):
        """使用 ChatSession 進行有記憶的對話"""
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

        try:
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
        except Exception as e:
            logger.error(
                f"Error during chat session with Vertex AI: {e}",
                exc_info=True)
            return "抱歉，AI 對話時發生錯誤，請稍後再試。", history
