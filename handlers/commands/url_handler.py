"""
URL 處理器
負責處理使用者傳送的 URL，並提供摘要或分析。
"""
import threading
from linebot.v3.messaging import MessagingApi, TextMessage, PushMessageRequest
from services.web_service import WebService
from services.ai.text_service import AITextService
from utils.logger import get_logger

logger = get_logger(__name__)


class URLHandler:
    """處理 URL 訊息的類別。"""

    def __init__(
            self,
            web_service: WebService,
            text_service: AITextService,
            line_bot_api: MessagingApi):
        self.web_service = web_service
        self.text_service = text_service
        self.line_bot_api = line_bot_api

    def is_url_message(self, text: str) -> bool:
        """檢查訊息是否為 URL。"""
        return text.startswith("http://") or text.startswith("https://")

    def handle(self, user_id: str, url: str):
        """處理 URL 訊息。"""
        def task():
            try:
                # 立即回覆，告知使用者正在處理
                initial_message = "收到您的網址了，正在為您分析摘要，請稍候..."
                self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=initial_message)]))

                # 爬取網頁內容
                content = self.web_service.scrape_text_from_url(url)
                if not content:
                    summary = "抱歉，無法讀取這個網址的內容。"
                else:
                    # 使用 AI 服務進行摘要
                    summary = self.text_service.summarize_text(content)

                # 推送最終摘要結果
                final_message = f"網址摘要：\n\n{summary}"
                self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=final_message)]))

            except Exception as e:
                logger.error(f"Error handling URL for user {user_id}: {e}", exc_info=True)
                error_message = "抱歉，處理網址時發生錯誤。"
                self.line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=error_message)]))

        threading.Thread(target=task).start()
