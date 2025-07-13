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

        try:
            chat_session = self.text_vision_model.start_chat(history=reconstructed_history)
            response = chat_session.send_message(user_message)
            cleaned_text = self.clean_text(response.text)
            
            # 拆解並回傳更新後的歷史紀錄
            updated_history = [{"role": c.role, "parts": [{"text": part.text} for part in c.parts]} for c in chat_session.history]
            return cleaned_text, updated_history
        except Exception as e:
            logger.error(f"Error during chat session with Vertex AI: {e}", exc_info=True)
            # 當 AI 呼叫失敗時，回傳一個錯誤訊息和「未更新」的歷史紀錄
            return "抱歉，AI 對話時發生錯誤，請稍後再試。", history

    def analyze_image(self, image_data: bytes):
        """分析圖片內容"""
        if not self.is_available():
            return "圖片分析功能未啟用。"
        
        image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
        prompt = """你是一位專業的圖片分析師。請用繁體中文，生動且詳細地描述這張圖片的內容。
你的分析應包含以下幾點：
1.  **主要物件與場景**：圖片中最顯眼的是什麼？發生了什麼事？
2.  **構圖與氛圍**：圖片的構圖如何？給人什麼樣的感覺或情緒？
3.  **文字識別**：如果圖片中有清晰可辨的文字，請將其完整列出。如果沒有，請忽略此點。
請將你的分析整理成一段流暢的描述。"""
        response = self.text_vision_model.generate_content([image_part, prompt])
        return self.clean_text(response.text)

    def translate_prompt_for_drawing(self, prompt_in_chinese):
        """將中文繪圖指令翻譯為英文"""
        if not self.is_available():
            return prompt_in_chinese
        try:
            translation_prompt = f'Translate the following Traditional Chinese text into a vivid, detailed English prompt for an AI image generation model like Imagen 3: "{prompt_in_chinese}"'
            response = self.text_vision_model.generate_content(translation_prompt)
            return self.clean_text(response.text)
        except Exception as e:
            logger.error(f"Prompt translation failed: {e}")
            return prompt_in_chinese

    def generate_image(self, prompt: str):
        """生成圖片"""
        if not self.image_gen_model:
            return None, "圖片生成功能未啟用。"
        try:
            response = self.image_gen_model.generate_images(prompt=prompt, number_of_images=1)
            return response.images[0]._image_bytes, "Vertex AI Imagen 繪圖成功！"
        except Exception as e:
            logger.error(f"Vertex AI image generation failed: {e}")
            return None, f"Vertex AI 畫圖時發生錯誤：{e}"

    def search_location(self, query: str, is_nearby=False, latitude=None, longitude=None):
        """搜尋地點或周邊"""
        if not self.is_available():
            return None

        # 定義 AI 必須回傳的 JSON 結構
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
            response = self.text_vision_model.generate_content(prompt)
            cleaned_response = self.clean_text(response.text)
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            # 為了方便除錯，記錄 AI 回傳的原始文字
            raw_response_text = "N/A"
            if 'response' in locals() and hasattr(response, 'text'):
                raw_response_text = response.text
            logger.error(f"Location search failed for query '{query}' due to JSONDecodeError: {e}. Raw AI response: '{raw_response_text}'", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during location search for query '{query}': {e}", exc_info=True)
            return None