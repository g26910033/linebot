def _handle_chat_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
    """處理一般對話"""
    try:
        # 1. 取得對話歷史
        history = self.storage_service.get_chat_history(user_id)
        
        # 2. 【核心修正】呼叫正確的函式名稱 `generate_text`
        response_text = self.ai_service.generate_text(message, history)
        
        # 如果 AI 服務回傳了有效的文字
        if response_text and "服務目前未啟用" not in response_text and "失敗" not in response_text:
            # 3. 【核心修正】手動更新對話歷史
            # 因為 generate_text 只回傳文字，我們需要自己將新的問與答加回歷史紀錄
            updated_history = history + [
                {"role": "user", "parts": [message]},
                {"role": "model", "parts": [response_text]}
            ]
            # 4. 儲存更新的歷史
            self.storage_service.save_chat_history(user_id, updated_history)
        
        # 5. 回覆訊息
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=response_text)])
        )
        
    except Exception as e:
        logger.error(f"[{user_id}] Chat process failed: {e}", exc_info=True)
        self._reply_error(line_bot_api, reply_token, "對話處理時發生錯誤，請稍後再試。")