"""
清除對話紀錄指令處理器
"""
from linebot.v3.messaging import MessagingApi, TextMessage
from services.storage_service import StorageService


class ClearMemoryHandler:
    """處理 '清除對話' 等指令的類別。"""

    def __init__(
            self,
            storage_service: StorageService,
            line_bot_api: MessagingApi):
        self.storage_service = storage_service
        self.line_bot_api = line_bot_api

    def handle(self, user_id: str, reply_token: str) -> None:
        """清除使用者的對話紀錄並回覆確認訊息。"""
        self.storage_service.clear_chat_history(user_id)
        self.line_bot_api.reply_message(
            reply_token=reply_token,
            messages=[TextMessage(text="好的，我們的對話記憶已經清除！")]
        )
