"""
AI 文字服務模組
負責處理所有與文字生成和處理相關的 AI 任務。
"""
import re
from .core import AICoreService
from services.web_service import WebService
from config.settings import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class AITextService:
    """
    AI 文字服務類別，封裝所有與文字相關的 AI 互動。
    """

    def __init__(self, config: AppConfig, core_service: AICoreService, web_service: WebService):
        self.config = config
        self.core_service = core_service
        self.web_service = web_service

    def summarize_text(self, text: str, max_length: int = 50000) -> str:
        """使用 AI 模型總結長篇文章"""
        if not self.core_service.is_available():
            return "AI 服務未啟用。"
        
        truncated_text = text[:max_length]

        prompt = f"""請你扮演一位專業的內容分析師。請用繁體中文，為以下文章產生一份約 200-300 字的精簡摘要，並在最後列出 3 個關鍵重點。
--- 文章開始 ---
{truncated_text}
--- 文章結束 ---"""
        response, _ = self.core_service.chat_with_history(prompt, [])
        return self.core_service.clean_text(response)

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
        response, _ = self.core_service.chat_with_history(prompt, [])
        return response.strip()

    def summarize_youtube_video(self, url: str) -> str:
        """
        獲取 YouTube 影片字幕並進行摘要。
        """
        logger.info(f"開始處理 YouTube 影片摘要: {url}")
        transcript = self.web_service.get_youtube_transcript(url)

        if not transcript or transcript in ["這部影片沒有可用的字幕。", "抱歉，獲取影片字幕時發生錯誤。"]:
            logger.warning(f"無法獲取字幕或字幕為空: {url}")
            # 如果沒有字幕，嘗試抓取網頁標題作為最後手段
            page_content = self.web_service.fetch_url_content(url)
            if page_content:
                # 簡單提取 <title> 標籤內容
                title_match = re.search(r'<title>(.*?)</title>', page_content, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else "影片"
                return f"抱歉，無法取得這部影片的字幕，因此無法提供摘要。\n影片標題為：「{title}」"
            return "抱歉，無法取得這部影片的字幕，也無法讀取其網頁內容。"

        logger.info(f"成功獲取字幕，長度為 {len(transcript)}。開始進行摘要...")
        summary = self.summarize_text(transcript)
        return f"✅ AI 影片摘要完成！\n\n{summary}"
