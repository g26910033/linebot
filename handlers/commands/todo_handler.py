"""
待辦事項指令處理器
"""
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest)
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class TodoCommandHandler:
    """處理待辦事項相關指令的類別。"""

    def __init__(self, storage_service: StorageService, configuration: Configuration):
        self.storage_service = storage_service
        self.configuration = configuration

    def _reply_message(self, reply_token: str, text: str):
        """統一的回覆訊息方法。"""
        with ApiClient(self.configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)]
            )
            line_bot_api.reply_message(reply_request)

    def handle_add(self, user_id: str, reply_token: str, item: str):
        """處理新增待辦事項。"""
        if not item:
            self._reply_message(reply_token, "請告訴我要新增什麼待辦事項喔！")
            return
        self.storage_service.add_todo_item(user_id, item)
        logger.info(f"Added todo '{item}' for user {user_id}")
        self._reply_message(reply_token, f"好的，已將「{item}」加入您的待辦清單！")

    def handle_list(self, user_id: str, reply_token: str):
        """處理列出待辦事項。"""
        items = self.storage_service.get_todo_items(user_id)
        if not items:
            self._reply_message(reply_token, "您的待辦清單目前是空的喔！")
            return

        # 格式化清單
        formatted_list = "您的待辦清單：\n"
        for i, item in enumerate(items, 1):
            formatted_list += f"{i}. {item}\n"
        
        self._reply_message(reply_token, formatted_list.strip())

    def handle_complete(self, user_id: str, reply_token: str, item: str):
        """處理完成待辦事項。"""
        if not item:
            self._reply_message(reply_token, "請告訴我要完成哪一項待辦事項喔！ (可以輸入編號或部分文字)")
            return
        
        success = self.storage_service.remove_todo_item(user_id, item)
        if success:
            logger.info(f"Completed todo '{item}' for user {user_id}")
            self._reply_message(reply_token, f"太棒了！已將「{item}」從您的待辦清單中移除。")
        else:
            self._reply_message(reply_token, f"找不到項目「{item}」，請檢查您的待辦清單。")
