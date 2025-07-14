"""
AI 圖像服務模組
負責處理所有與圖像生成和分析相關的 AI 任務。
"""
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
        self._initialize_model()

    def _initialize_model(self):
        """初始化圖像生成模型"""
        try:
            if self.config.image_model_name:
                # 確保使用完整的模型路徑
                model_path = (
                    f"projects/{self.config.gcp_project_id}/locations/"
                    f"{self.config.gcp_location}/publishers/google/models/"
                    f"{self.config.image_model_name}"
                )
                self.image_gen_model = ImageGenerationModel.from_pretrained(
                    model_path)
                logger.info(
                    f"Image generation model '{model_path}' loaded for AIImageService.")
        except Exception as e:
            logger.error(
                f"AIImageService model initialization failed: {e}",
                exc_info=True)

    def is_available(self) -> bool:
        """檢查圖像生成模型是否可用"""
        return self.image_gen_model is not None

    def analyze_image(self, image_data: bytes) -> str:
        """分析圖片內容"""
        if not self.core_service.is_available():
            return "圖片分析功能未啟用。"

        image_part = Part.from_data(data=image_data, mime_type="image/jpeg")
        prompt = (
            "你是一位專業的圖片分析師。請用繁體中文，生動且詳細地描述這張圖片的內容。\n"
            "你的分析應包含以下幾點：\n"
            "1.  **主要物件與場景**：圖片中最顯眼的是什麼？發生了什麼事？\n"
            "2.  **構圖與氛圍**：圖片的構圖如何？給人什麼樣的感覺或情緒？\n"
            "3.  **文字識別**：如果圖片中有清晰可辨的文字，請將其完整列出。如果沒有，請忽略此點。\n"
            "請將你的分析整理成一段流暢的描述。")
        response = self.core_service.text_vision_model.generate_content(
            [image_part, prompt])
        return self.core_service.clean_text(response.text)

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
        """生成圖片"""
        if not self.is_available():
            return None, "圖片生成功能未啟用。"
        try:
            response = self.image_gen_model.generate_images(
                prompt=prompt, number_of_images=1)
            return response.images[0]._image_bytes, "Vertex AI Imagen 繪圖成功！"
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

            # safety_settings is not currently used in the edit_image call
            # according to the latest documentation. If needed in the future,
            # it can be passed as a parameter.
            response = self.image_gen_model.edit_image(
                base_image=base_image,
                prompt=translated_prompt,
                number_of_images=1
            )
            return response.images[0]._image_bytes, "以圖生圖成功！"
        except Exception as e:
            logger.error(f"Vertex AI image-to-image generation failed: {e}")
            return None, f"以圖生圖時發生錯誤：{e}"
