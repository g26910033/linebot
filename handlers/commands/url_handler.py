"""
URL 處理器
負責處理使用者傳送的 URL，並提供摘要或分析。
"""
import threading
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, PushMessageRequest
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
            configuration: Configuration):
        self.web_service = web_service
        self.text_service = text_service
        self.configuration = configuration

    def is_url_message(self, text: str) -> bool:
        """檢查訊息是否為 URL。"""
        return text.startswith("http://") or text.startswith("https://")

    def handle(self, user_id: str, url: str):
        """處理 URL 訊息。"""
        def task():
            try:
                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    # 立即回覆，告知使用者正在處理
                    initial_message = "收到您的網址了，正在為您分析摘要，請稍候..."
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=initial_message)]))

                # 爬取網頁內容
                content = self.web_service.scrape_text_from_url(url)
                if not content:
                    summary = "抱歉，無法讀取這個網址的內容。"
                else:
                    # 使用 AI 服務進行摘要
                    summary = self.text_service.summarize_text(content)

                with ApiClient(self.configuration) as api_client:
                    line_bot_api = MessagingApi(api_client)
                    # 推送最終摘要結果
                    final_message = f"網址摘要：\n\n{summary}"
                    line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=final_message)]))

            except Exception as e:
                logger.error(f"Error handling URL for user {user_id}: {e}", exc_info=True)
                try:
                    with ApiClient(self.configuration) as api_client:
                        line_bot_api = MessagingApi(api_client)
                        error_message = "抱歉，處理網址時發生錯誤。"
                        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=error_message)]))
                except Exception as api_e:
                    logger.error(f"Failed to send error message to user {user_id}: {api_e}", exc_info=True)

        threading.Thread(target=task).start()
