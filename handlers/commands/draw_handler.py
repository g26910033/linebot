"""
AI 繪圖指令處理器
"""
import threading
from linebot.v3.messaging import MessagingApi, TextMessage, ImageMessage
from services.ai.image_service import AIImageService
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)

class DrawCommandHandler:
    """處理 '畫' 指令的類別。"""

    def __init__(self, image_service: AIImageService, storage_service: StorageService, line_bot_api: MessagingApi):
        self.image_service = image_service
        self.storage_service = storage_service
        self.line_bot_api = line_bot_api
        # 假設 MessageHandler 的一些輔助方法可以被重用或重新實現
        # 為了簡單起見，我們在這裡直接使用 line_bot_api
        # 在一個更完整的重構中，這些輔助方法也應該被提取出來
        self.line_channel_access_token = None # 需要從主應用程式傳入

    def handle(self, user_id: str, reply_token: str, prompt: str) -> None:
        """處理繪圖指令。"""
        if not prompt:
            self.line_bot_api.reply_message(
                reply_token=reply_token,
                messages=[TextMessage(text="請告訴我要畫什麼喔！\n格式：`畫 一隻可愛的貓`")]
            )
            return

        # 這裡我們不能直接回覆，因為原始邏輯是異步的
        # 我們將啟動一個線程來處理，並立即返回
        # loading animation 和 push message 需要 access token，這需要在初始化時傳入
        
        # 顯示加載動畫 (這部分邏輯需要從 MessageHandler 提取或重構)
        # self._show_loading_animation(user_id, seconds=30)

        def task(user_id, prompt):
            try:
                # self._push_message_with_retry(user_id, messages=[TextMessage(text=f"好的，正在為您繪製「{prompt}」，請稍候...")])
                translated_prompt = self.image_service.translate_prompt_for_drawing(prompt)
                image_bytes, status_msg = self.image_service.generate_image(translated_prompt)
                
                if image_bytes:
                    image_url, upload_status = self.storage_service.upload_image(image_bytes)
                    if image_url:
                        messages = [ImageMessage(originalContentUrl=image_url, previewImageUrl=image_url)]
                    else:
                        messages = [TextMessage(text=f"圖片上傳失敗: {upload_status}")]
                else:
                    messages = [TextMessage(text=f"繪圖失敗: {status_msg}")]
                
                # 使用 push_message 而不是 reply_message，因為原始的 token 可能已經過期
                self.line_bot_api.push_message(to=user_id, messages=messages)

            except Exception as e:
                logger.error(f"Error in drawing task for user {user_id}: {e}", exc_info=True)
                self.line_bot_api.push_message(to=user_id, messages=[TextMessage(text="繪圖時發生了未預期的錯誤。")])

        threading.Thread(target=task, args=(user_id, prompt)).start()
