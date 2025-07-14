"""
功能說明指令處理器
"""
import os
from linebot.v3.messaging import (
    MessagingApi, TextMessage, ReplyMessageRequest)
from utils.logger import get_logger

logger = get_logger(__name__)


class HelpCommandHandler:
    """處理 'help' 或 '功能說明' 指令的類別。"""

    def __init__(self, line_bot_api: MessagingApi):
        self.line_bot_api = line_bot_api
        self.help_text = self._load_help_text()

    def _load_help_text(self) -> str:
        """從檔案載入功能說明的文字。"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(base_dir, "help_text.md")
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"help_text.md not found at {file_path}")
            return "抱歉，功能說明文件遺失了。"

    def handle(self, reply_token: str):
        """處理指令並回覆功能說明的文字。"""
        reply_request = ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=self.help_text)]
        )
        self.line_bot_api.reply_message(reply_request)
