"""
AI 圖像服務模組
負責處理所有與圖像生成和分析相關的 AI 任務。
"""
import hashlib
from vertexai.generative_models import Part
from vertexai.preview.vision_models import Image, ImageGenerationModel
from config.settings import AppConfig
from utils.logger import get_logger
from .core import AICoreService

logger = get_logger(__name__)


class AIImageService:
    """
    AI 圖像服務類別，封裝所有與圖像相關的 AI 互動。
    """

    def __init__(self, config: AppConfig, core_service: AICoreService):
        self.config = config
        self.core_service = core_service
        self.image_gen_model = None
        self.storage_service = None  # 將在需要時注入
        self._initialize_model()

    def set_storage_service(self, storage_service):
        """注入儲存服務以使用快取功能"""
        self.storage_service = storage_service

    def _initialize_model(self):
        """初始化圖像生成模型"""
        if not self.config.image_model_name:
            logger.warning("Image model name not configured. AIImageService will be disabled.")
            return
        try:
            logger.info(f"Attempting to load ImageGenerationModel: {self.config.image_model_name}")
            self.image_gen_model = ImageGenerationModel.from_pretrained(self.config.image_model_name)
            logger.info(f"Image generation model '{self.config.image_model_name}' loaded successfully.")
        except Exception as e:
            logger.critical(
                f"CRITICAL: AIImageService model initialization failed: {e}",
                exc_info=True)
            self.image_gen_model = None
        finally:
            logger.info(f"Final state of image_gen_model: {self.image_gen_model}")

    def is_available(self) -> bool:
        """檢查圖像生成模型是否可用"""
        return self.image_gen_model is not None

    def analyze_image(self, image_data: bytes) -> str:
        """分析圖片內容，使用快取機制"""
        if not self.core_service.is_available():
            return "圖片分析功能未啟用。"

        # 生成圖片雜湊值用於快取
        image_hash = hashlib.md5(image_data).hexdigest()
        
        # 檢查快取
        if self.storage_service:
            cached_result = self.storage_service.get_cached_image_analysis(image_hash)
            if cached_result:
                logger.info(f"使用快取的圖片分析結果: {image_hash[:8]}...")
                return cached_result

        image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
        prompt = (
            "你是一位專業的圖片分析師。請用繁體中文，生動且詳細地描述這張圖片的內容。\n"
            "你的分析應包含以下幾點：\n"
            "1.  **主要物件與場景**：圖片中最顯眼的是什麼？發生了什麼事？\n"
            "2.  **構圖與氛圍**：圖片的構圖如何？給人什麼樣的感覺或情緒？\n"
            "3.  **文字識別**：如果圖片中有清晰可辨的文字，請將其完整列出。如果沒有，請忽略此點。\n"
            "請將你的分析整理成一段流暢的描述。")
        
        try:
            response = self.core_service.text_vision_model.generate_content(
                [image_part, prompt])
            result = self.core_service.clean_text(response.text)
            
            # 儲存到快取
            if self.storage_service:
                self.storage_service.cache_image_analysis(image_hash, result)
                logger.info(f"圖片分析結果已快取: {image_hash[:8]}...")
            
            return result
        except Exception as e:
            logger.error(f"圖片分析失敗: {e}")
            return "抱歉，圖片分析時發生錯誤，請稍後再試。"

    def translate_prompt_for_drawing(self, prompt_in_chinese: str) -> str:
        """將中文繪圖指令翻譯為英文"""
        if not self.core_service.is_available():
            return prompt_in_chinese
        try:
            translation_prompt = (
                'Translate the following Traditional Chinese text into a '
                'vivid, detailed English prompt for an AI image generation '
                f'model like Imagen 3: "{prompt_in_chinese}"'
            )
            response = self.core_service.text_vision_model.generate_content(
                translation_prompt)
            return self.core_service.clean_text(response.text)
        except Exception as e:
            logger.error(f"Prompt translation failed: {e}")
            return prompt_in_chinese

    def generate_image(self, prompt: str):
        """生成圖片，使用快取機制"""
        if not self.is_available():
            return None, "圖片生成功能未啟用。"
        
        # 生成提示詞雜湊值用於快取
        prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
        
        # 檢查快取 (僅檢查 URL，不快取圖片二進位資料)
        if self.storage_service:
            cached_url = self.storage_service.get_cached_generated_image(prompt_hash)
            if cached_url:
                logger.info(f"使用快取的生成圖片 URL: {prompt_hash[:8]}...")
                # 注意：這裡返回 URL 而不是二進位資料
                return cached_url, "使用快取的圖片生成結果！"
        
        try:
            response = self.image_gen_model.generate_images(
                prompt=prompt, number_of_images=1)
            if not response.images:
                logger.warning(f"Image generation returned no images for prompt: {prompt}")
                return None, "抱歉，AI 無法根據您的提示生成圖片，請換個說法試試看。"
            
            image_bytes = response.images[0]._image_bytes
            
            # 上傳到 Cloudinary 並快取 URL
            if self.storage_service:
                from services.storage_service import StorageService
                if hasattr(self.storage_service, 'upload_image'):
                    image_url, error = self.storage_service.upload_image(image_bytes)
                    if image_url:
                        self.storage_service.cache_generated_image(prompt_hash, image_url)
                        logger.info(f"圖片已上傳並快取 URL: {prompt_hash[:8]}...")
                        return image_url, "Vertex AI Imagen 繪圖成功！"
            
            return image_bytes, "Vertex AI Imagen 繪圖成功！"
        except Exception as e:
            logger.error(f"Vertex AI image generation failed: {e}")
            return None, f"Vertex AI 畫圖時發生錯誤：{e}"

    def generate_image_from_image(self, base_image_bytes: bytes, prompt: str):
        """根據基礎圖片和文字提示生成新圖片"""
        if not self.is_available():
            return None, "圖片生成功能未啟用。"
        try:
            base_image = Image(image_bytes=base_image_bytes)
            translated_prompt = self.translate_prompt_for_drawing(prompt)

            response = self.image_gen_model.edit_image(
                base_image=base_image,
                prompt=translated_prompt,
                number_of_images=1
            )
            if not response.images:
                logger.warning(f"Image editing returned no images for prompt: {prompt}")
                return None, "抱歉，AI 無法根據您的提示修改圖片，請換個說法試試看。"
            return response.images[0]._image_bytes, "以圖生圖成功！"
        except Exception as e:
            logger.error(f"Vertex AI image-to-image generation failed: {e}")
            return None, f"以圖生圖時發生錯誤：{e}"
