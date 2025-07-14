"""
功能說明指令處理器
"""
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
            # 這邊的路徑是相對於專案根目錄，需要注意
            # 在伺服器環境中可能需要調整為絕對路徑
            with open("handlers/commands/help_text.md", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.error("help_text.md not found.")
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
