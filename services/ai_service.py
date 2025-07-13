"""
AI 服務模組
負責與 Google Vertex AI 溝通，處理所有 AI 相關任務。
"""
import re
import json
import pytz
from datetime import datetime
from config.settings import AppConfig
from utils.logger import get_logger

# 引入所有需要的 Vertex AI 工具
import vertexai
from vertexai.generative_models import GenerativeModel, Part, Content, HarmCategory, HarmBlockThreshold
from vertexai.preview.vision_models import Image, ImageGenerationModel

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

    def summarize_text(self, text: str, max_length: int = 50000):
        """使用 AI 模型總結長篇文章"""
        if not self.is_available():
            return "AI 服務未啟用。"
        
        # 截斷過長的文本以符合模型限制
        truncated_text = text[:max_length]

        prompt = f"""請你扮演一位專業的內容分析師。請用繁體中文，為以下文章產生一份約 200-300 字的精簡摘要，並在最後列出 3 個關鍵重點。
--- 文章開始 ---
{truncated_text}
--- 文章結束 ---"""
        response = self.text_vision_model.generate_content(prompt)
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

    def generate_image_from_image(self, base_image_bytes: bytes, prompt: str):
        """根據基礎圖片和文字提示生成新圖片"""
        if not self.image_gen_model:
            return None, "圖片生成功能未啟用。"
        try:
            base_image = Image(image_bytes=base_image_bytes)
            # 將中文提示翻譯為英文，以獲得更好的效果
            translated_prompt = self.translate_prompt_for_drawing(prompt)
            
            # 引入安全設定，嘗試降低被阻擋的機率
            safety_settings = {
                HarmCategory.HARM_CATEGORY_UNSPECIFIED: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            }

            response = self.image_gen_model.edit_image(
                base_image=base_image,
                prompt=translated_prompt,
                number_of_images=1,
                safety_settings=safety_settings,
            )
            return response.images[0]._image_bytes, "以圖生圖成功！"
        except Exception as e:
            logger.error(f"Vertex AI image-to-image generation failed: {e}")
            return None, f"以圖生圖時發生錯誤：{e}"

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

    def translate_text(self, user_message: str) -> str:
        """
        使用 AI 模型從自然語言中解析並翻譯文字。
        """
        if not self.is_available():
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
            response = self.text_vision_model.generate_content(prompt)
            # 這裡不需要 clean_text，因為提示已經要求純文字
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error during smart translation: {e}", exc_info=True)
            return "抱歉，翻譯時發生錯誤。"

    def parse_event_from_text(self, text: str) -> dict | None:
        """
        從自然語言中解析出事件的標題、開始時間和結束時間。
        """
        if not self.is_available():
            return None

        # 獲取當前時間並格式化，作為 AI 的參考基準
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
            response = self.text_vision_model.generate_content(prompt)
            cleaned_response = self.clean_text(response.text)
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"Error parsing event from text: {e}", exc_info=True)
            return None
