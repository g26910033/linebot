"""
網址處理器
"""
import re
import threading
from linebot.v3.messaging import MessagingApi, TextMessage
from services.web_service import WebService
from services.ai.text_service import AITextService
from utils.logger import get_logger

logger = get_logger(__name__)


class URLHandler:
    """處理包含網址的訊息。"""
    URL_PATTERN = re.compile(r'https?://\S+')

    def __init__(
            self,
            web_service: WebService,
            text_service: AITextService,
            line_bot_api: MessagingApi):
        self.web_service = web_service
        self.text_service = text_service
        self.line_bot_api = line_bot_api

    def is_url_message(self, text: str) -> bool:
        """檢查訊息是否為網址。"""
        return self.URL_PATTERN.match(text) is not None

    def handle(self, user_id: str, user_message: str):
        """處理網址訊息，進行摘要。"""
        if not self.web_service:
            self.line_bot_api.push_message(
                to=user_id, messages=[
                    TextMessage(
                        text="抱歉，網頁/影片摘要服務目前未啟用。")])
            return

        url_match = self.URL_PATTERN.search(user_message)
        if not url_match:
            # This case should ideally not be reached if called after
            # is_url_message check
            return

        url = url_match.group(0)

        # self._show_loading_animation(user_id, seconds=30) # Loading animation
        # logic needs to be centralized

        def task(user_id, url):
            try:
                content = self.web_service.fetch_url_content(url)
                if not content:
                    self.line_bot_api.push_message(
                        to=user_id, messages=[
                            TextMessage(
                                text="抱歉，無法讀取您提供的網址內容。")])
                    return

                summary = self.text_service.summarize_text(content)
                self.line_bot_api.push_message(
                    to=user_id, messages=[TextMessage(text=summary)])
            except Exception as e:
                logger.error(
                    f"Error in URL message handling task for user {user_id}: {e}",
                    exc_info=True)
                self.line_bot_api.push_message(
                    to=user_id, messages=[
                        TextMessage(
                            text="哎呀，摘要網頁/影片內容時發生錯誤了，請稍後再試。")])

        threading.Thread(target=task, args=(user_id, url)).start()
