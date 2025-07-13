"""
AI 服務模組
負責處理所有 AI 相關功能
"""
import json
import re
from typing import Optional, List, Dict, Any, Tuple
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part, Content
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account

from config.settings import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class AIService:
    """AI 服務類別"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.text_vision_model: Optional[GenerativeModel] = None
        self.image_gen_model: Optional[ImageGenerationModel] = None
        self._initialize_models()
    
    def _initialize_models(self) -> None:
        """初始化 AI 模型"""
        try:
            credentials_info = json.loads(self.config.gcp_service_account_json)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            
            vertexai.init(
                project=self.config.gcp_project_id,
                location=self.config.gcp_location,
                credentials=credentials
            )
            
            self.text_vision_model = GenerativeModel(self.config.text_model_name)
            self.image_gen_model = ImageGenerationModel.from_pretrained(self.config.image_model_name)
            
            logger.info("AI models initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
            raise
    
    def is_available(self) -> bool:
        """檢查 AI 服務是否可用"""
        return self.text_vision_model is not None and self.image_gen_model is not None
    
    def clean_text(self, text: str) -> str:
        """清理 AI 回應文字"""
        cleaned_text = re.sub(r'```json\n|```', '', text)
        cleaned_text = re.sub(r'[*#]', '', cleaned_text)
        return cleaned_text.strip()
    
    def translate_prompt_for_image_generation(self, chinese_prompt: str) -> str:
        """將中文提示詞翻譯為英文圖片生成提示詞"""
        if not self.text_vision_model:
            return chinese_prompt
        
        try:
            translation_prompt = (
                f'Translate the following Traditional Chinese text into a vivid, '
                f'detailed English prompt for an AI image generation model like Imagen 3. '
                f'Focus on cinematic and artistic keywords. '
                f'Only output the English prompt: "{chinese_prompt}"'
            )
            
            response = self.text_vision_model.generate_content(translation_prompt)
            return self.clean_text(response.text)
            
        except Exception as e:
            logger.error(f"Prompt translation failed: {e}")
            return chinese_prompt
    
    def generate_image(self, prompt: str) -> Tuple[Optional[bytes], str]:
        """生成圖片"""
        if not self.image_gen_model:
            return None, "圖片生成功能未啟用"
        
        try:
            response = self.image_gen_model.generate_images(
                prompt=prompt,
                number_of_images=1
            )
            return response.images[0]._image_bytes, "圖片生成成功"
            
        except Exception as e:
            error_msg = f"圖片生成失敗: {e}"
            logger.error(error_msg)
            return None, error_msg
    
    def analyze_image(self, image_data: bytes, prompt: str = None) -> str:
        """分析圖片內容"""
        if not self.text_vision_model:
            return "圖片分析功能未啟用"
        
        try:
            image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
            analysis_prompt = prompt or "請用繁體中文，詳細描述這張圖片的內容。"
            
            response = self.text_vision_model.generate_content([image_part, analysis_prompt])
            return self.clean_text(response.text)
            
        except Exception as e:
            error_msg = f"圖片分析失敗: {e}"
            logger.error(error_msg)
            return error_msg
    
    def search_location(self, query: str) -> Optional[Dict[str, str]]:
        """搜尋地點資訊"""
        if not self.text_vision_model:
            return None
        
        try:
            search_prompt = f"""
            You are a professional location search and data organization assistant. 
            Based on the user's query, find the single most relevant location.
            Your response MUST be a single JSON object containing three keys:
            1. "name": The official name of the location.
            2. "address": The full address of the location.
            3. "phone_number": The contact phone number. If no phone number is found, 
               the value for this key must be the string "無提供電話".
            Strictly adhere to the JSON format. Do not return any extra text or explanations.
            User's query: "{query}"
            """
            
            response = self.text_vision_model.generate_content(search_prompt)
            return json.loads(self.clean_text(response.text))
            
        except Exception as e:
            logger.error(f"Location search failed: {e}")
            return None
    
    def search_nearby_locations(
        self, 
        latitude: float, 
        longitude: float, 
        keyword: str = "餐廳"
    ) -> Optional[List[Dict[str, str]]]:
        """搜尋附近地點"""
        if not self.text_vision_model:
            return None
        
        try:
            search_prompt = f"""
            You are a professional local guide and map search engine. 
            Based on the user's provided latitude and longitude, find the {self.config.max_search_results} 
            closest locations that match the query: "{keyword}".
            You MUST sort the results strictly by geographical distance, not by popularity, ratings, or any other factor.
            The search radius should be approximately {self.config.search_radius_km} kilometers.
            Your response MUST be a JSON array, where each object in the array contains "name", "address", and "phone_number".
            If a phone number is not found for a location, the value for "phone_number" must be the string "無提供電話".
            Strictly adhere to the JSON format. Do not return any extra text or explanations.
            User's location: Latitude {latitude}, Longitude {longitude}
            """
            
            response = self.text_vision_model.generate_content(search_prompt)
            return json.loads(self.clean_text(response.text))
            
        except Exception as e:
            logger.error(f"Nearby search failed: {e}")
            return None
    
    def chat_with_history(self, message: str, history: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """與 AI 對話並維護歷史記錄"""
        if not self.text_vision_model:
            return "AI 服務未啟用", history
        
        try:
            # 重建對話歷史
            reconstructed_history = []
            for msg in history:
                role = msg.get("role")
                parts_list = [
                    Part.from_text(p.get("text", "")) if isinstance(p, dict) else Part.from_text(p)
                    for p in msg.get("parts", [])
                ]
                if role and parts_list:
                    reconstructed_history.append(Content(role=role, parts=parts_list))
            
            # 開始對話
            chat_session = self.text_vision_model.start_chat(history=reconstructed_history)
            response = chat_session.send_message(message)
            
            # 更新歷史記錄
            updated_history = [
                {
                    "role": content.role,
                    "parts": [{"text": part.text} for part in content.parts]
                }
                for content in chat_session.history
            ]
            
            return self.clean_text(response.text), updated_history
            
        except Exception as e:
            error_msg = f"對話處理失敗: {e}"
            logger.error(error_msg)
            return error_msg, history