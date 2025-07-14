"""
功能說明指令處理器
"""
import os
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest)
from utils.logger import get_logger

logger = get_logger(__name__)


class HelpCommandHandler:
    """處理 'help' 或 '功能說明' 指令的類別。"""

    def __init__(self, configuration: Configuration):
        self.configuration = configuration
        self.help_text = self._load_help_text()

    def _load_help_text(self) -> str:
        """從檔案載入功能說明的文字。"""
        try:
            # 使用相對於此檔案的絕對路徑，確保穩定性
            base_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(base_dir, "help_text.md")
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"help_text.md not found at {file_path}")
            return "抱歉，功能說明文件遺失了。"

    def handle(self, reply_token: str):
        """處理指令並回覆功能說明的文字。"""
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=self.help_text)]
            )
            line_bot_api.reply_message(reply_request)
