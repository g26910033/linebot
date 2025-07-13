"""
AI 服務模組
負責與 Google Vertex AI 溝通，處理所有 AI 相關任務。
"""
import re
import json
from config.settings import AppConfig
from utils.logger import get_logger

# 引入所有需要的 Vertex AI 工具
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part, Content
from vertexai.preview.vision_models import ImageGenerationModel

logger = get_logger(__name__)

class AIService:
    """
    AI 服務類別，封裝所有與 Vertex AI 的真實互動。
    """
    def __init__(self, config: AppConfig):
        self.config = config
        self.text_vision_model = None
        self.image_gen_model = None
        self._initialize_models()

    def _initialize_models(self):
        """根據設定初始化所有 AI 模型"""
        try:
            # 假設 vertexai.init() 已在主應用程式 (app.py) 中完成
            if self.config.text_model_name:
                self.text_vision_model = GenerativeModel(self.config.text_model_name)
                logger.info(f"Text/Vision model '{self.config.text_model_name}' loaded.")
            if self.config.image_model_name:
                self.image_gen_model = ImageGenerationModel.from_pretrained(self.config.image_model_name)
                logger.info(f"Image generation model '{self.config.image_model_name}' loaded.")
        except Exception as e:
            logger.error(f"AI Service model initialization failed: {e}", exc_info=True)

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
        
        # 組裝歷史紀錄
        reconstructed_history = []
        if history:
            for msg in history:
                role = msg.get("role")
                parts = [Part.from_text(p.get("text", "")) for p in msg.get("parts", [])]
                if role and parts:
                    reconstructed_history.append(Content(role=role, parts=parts))

        chat_session = self.text_vision_model.start_chat(history=reconstructed_history)
        response = chat_session.send_message(user_message)
        cleaned_text = self.clean_text(response.text)
        
        # 拆解並回傳更新後的歷史紀錄
        updated_history = [{"role": c.role, "parts": [{"text": p.text}]} for c in chat_session.history]
        return cleaned_text, updated_history

    def analyze_image(self, image_data: bytes):
        """分析圖片內容"""
        if not self.is_available():
            return "圖片分析功能未啟用。"
        
        image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
        prompt = "請用繁體中文，詳細描述這張圖片的內容。"
        response = self.text_vision_model.generate_content([image_part, prompt])
        return self.clean_text(response.text)

    # ... (此處省略其他 AI 相關函式如 translate_prompt, generate_image, search_location 等)
    # ... (請確保您將之前 main.py 中的這些工作函式也一併轉移過來)