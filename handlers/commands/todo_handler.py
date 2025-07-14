"""
待辦事項指令處理器
"""
import re
from linebot.v3.messaging import (
    MessagingApi, TextMessage, ReplyMessageRequest)
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class TodoCommandHandler:
    """處理所有待辦事項相關指令的類別。"""

    def __init__(
            self,
            storage_service: StorageService,
            line_bot_api: MessagingApi):
        self.storage_service = storage_service
        self.line_bot_api = line_bot_api
        # Flex Message 的建立邏輯也需要從 MessageHandler 提取
        # 暫時在這裡重新實現
        self.line_channel_access_token = None

    def handle_add(self, user_id: str, reply_token: str, item: str):
        """處理新增待辦事項。"""
        if not item:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="請告訴我要新增什麼待辦事項喔！\n格式：`新增待辦 買牛奶`")]
            )
            self.line_bot_api.reply_message(reply_request)
            return
        if self.storage_service.add_todo_item(user_id, item):
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，已將「{item}」加入您的待辦清單！")]
            )
            self.line_bot_api.reply_message(reply_request)
        else:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="抱歉，新增待辦事項時發生錯誤。")]
            )
            self.line_bot_api.reply_message(reply_request)

    def handle_list(self, user_id: str, reply_token: str):
        """處理列出待辦事項。"""
        todo_list = self.storage_service.get_todo_list(user_id)
        if not todo_list:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="您的待辦清單是空的！")]
            )
            self.line_bot_api.reply_message(reply_request)
        else:
            # flex_message_dict = self._create_todo_list_flex_message(todo_list)
            # _reply_flex_message 邏輯需要被提取或重構
            # 暫時簡化處理
            list_text = "這是您的待辦清單：\n" + \
                "\n".join(f"{i + 1}. {item}" for i,
                          item in enumerate(todo_list))
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=list_text)]
            )
            self.line_bot_api.reply_message(reply_request)

    def handle_complete(self, user_id: str, reply_token: str, text: str):
        """處理完成待辦事項。"""
        match = re.search(r'\d+', text)
        item_index = int(match.group(0)) - 1 if match else -1

        if item_index < 0:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="請告訴我要完成哪一項喔！\n格式：`完成待辦 1`")]
            )
            self.line_bot_api.reply_message(reply_request)
            return

        removed_item = self.storage_service.remove_todo_item(
            user_id, item_index)
        if removed_item is not None:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"太棒了！已完成項目：「{removed_item}」")]
            )
            self.line_bot_api.reply_message(reply_request)
        else:
            reply_request = ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text="找不到您指定的待辦事項，請檢查編號是否正確。")]
            )
            self.line_bot_api.reply_message(reply_request)

    def _create_todo_list_flex_message(self, todo_list: list) -> dict:
        # 這裡的 Flex Message 邏輯是從 message_handlers.py 複製過來的
        # 在完整的重構中，這應該被提取到一個共用的 UI/template 模組中
        body_contents = []
        for i, item in enumerate(todo_list[:10]):
            body_contents.append({
                "type": "box", "layout": "horizontal", "spacing": "md",
                "contents": [
                    {"type": "text", "text": f"{i + 1}. {item}",
                        "wrap": True, "flex": 4},
                    {
                        "type": "button", "style": "primary",
                        "height": "sm", "flex": 1,
                        "action": {
                            "type": "postback", "label": "完成",
                            "data": f"action=complete_todo&index={i}",
                            "displayText": f"完成待辦 {i + 1}"},
                        "color": "#1DB446"}]})
            if i < len(todo_list[:10]) - 1:
                body_contents.append({"type": "separator", "margin": "md"})

        return {
            "type": "bubble",
            "header": {
                "type": "box", "layout": "vertical",
                "contents": [
                    {
                        "type": "text", "text": "📝 您的待辦清單", "weight": "bold",
                        "size": "xl", "color": "#1DB446"}]},
            "body": {
                "type": "box", "layout": "vertical", "spacing": "md",
                "contents": body_contents}}
