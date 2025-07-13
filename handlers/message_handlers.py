    """
訊息處理器模組
負責處理不同類型的 LINE 訊息
"""
import threading
from urllib.parse import quote_plus
from typing import List, Dict, Any

from linebot.v3.messaging import (
    MessagingApi, MessagingApiBlob,
    ReplyMessageRequest, PushMessageRequest,
    TextMessage, ImageMessage, TemplateMessage,
    CarouselTemplate, CarouselColumn, URIAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent

from services.ai_service import AIService
from services.storage_service import StorageService
from utils.logger import get_logger

logger = get_logger(__name__)


class MessageHandler:
    """訊息處理器基類"""
    
    def __init__(self, ai_service: AIService, storage_service: StorageService):
        self.ai_service = ai_service
        self.storage_service = storage_service

    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        """回覆錯誤訊息"""
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
        )

    def _create_location_carousel(self, places_list: List[Dict[str, str]], line_bot_api: MessagingApi, user_id: str) -> None:
        """建立地點輪播訊息
        最多顯示 5 個地點。
        """
        if not places_list:
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，找不到符合條件的地點。")])
            )
            return
        
        columns = []
        for place in places_list[:5]:  # 最多顯示 5 個地點
            place_name = place.get("name")
            place_address = place.get("address")
            phone_number = place.get("phone_number", "無提供電話")
            
            if not all([place_name, place_address]):
                # Skip if essential information is missing
                continue
            
            encoded_query = quote_plus(f"{place_name} {place_address}")
            map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            display_text = f"{place_address}\n電話：{phone_number}"
            
            column = CarouselColumn(
                title=place_name,
                text=display_text[:60],  # LINE API 限制文字長度
                actions=[URIAction(label='在地圖上打開', uri=map_url)]
            )
            columns.append(column)
        
        if columns:
            template_message = TemplateMessage(
                alt_text='為您找到推薦地點！',
                template=CarouselTemplate(columns=columns)
            )
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[template_message])
            )
        else:
            # If no valid columns could be created from the places_list
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，AI 回傳的資料格式有誤，無法為您顯示地點。")])
            )


class TextMessageHandler(MessageHandler):
    """文字訊息處理器"""

    CLEAR_COMMANDS = ["清除對話", "忘記對話", "清除記憶"]
    DRAW_COMMAND_PREFIX = "畫"
    SEARCH_COMMAND_PREFIXES = ["搜尋", "尋找"]

    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        """處理文字訊息"""
        user_message = event.message.text.strip()
        reply_token = event.reply_token
        user_id = event.source.user_id
        
        if not self.ai_service.is_available():
            self._reply_error(line_bot_api, reply_token, "AI 服務未啟用")
            return
        
        # 處理不同類型的指令
        if self._is_clear_command(user_message):
            self._handle_clear_command(line_bot_api, reply_token, user_id)
        elif self._is_draw_command(user_message):
            self._handle_draw_command(line_bot_api, reply_token, user_id, user_message)
        elif self._is_search_command(user_message):
            self._handle_search_command(line_bot_api, reply_token, user_id, user_message)
        else:
            self._handle_chat_command(line_bot_api, reply_token, user_id, user_message)
    
    def _is_clear_command(self, message: str) -> bool:
        """檢查是否為清除對話指令"""
        return message.lower() in [keyword.lower() for keyword in self.CLEAR_COMMANDS]
    
    def _is_draw_command(self, message: str) -> bool:
        """檢查是否為繪圖指令"""
        return message.startswith(self.DRAW_COMMAND_PREFIX)
    
    def _is_search_command(self, message: str) -> bool:
        """檢查是否為搜尋指令"""
        return any(message.startswith(keyword) for keyword in self.SEARCH_COMMAND_PREFIXES)
    
    def _handle_clear_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str) -> None:
        """處理清除對話指令"""
        success = self.storage_service.clear_chat_history(user_id)
        message = "好的，我已經將我們先前的對話紀錄都忘記了。" if success else "清除對話記錄時發生錯誤。"
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)])
        )
    
    def _handle_draw_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
        """處理繪圖指令"""
        prompt_chinese = message.split(self.DRAW_COMMAND_PREFIX, 1)[1].strip()
        if not prompt_chinese:
            self._reply_error(line_bot_api, reply_token, "請提供繪圖描述，例如：畫 一隻可愛的貓")
            return
        
        # 回覆確認訊息
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，收到繪圖指令：「{prompt_chinese}」。\n正在翻譯並生成圖片...")]
            )
        )
        
        # 在背景處理圖片生成
        threading.Thread(
            target=self._process_image_generation,
            args=(line_bot_api, user_id, prompt_chinese)
        ).start()
    
    def _process_image_generation(self, line_bot_api: MessagingApi, user_id: str, prompt_chinese: str) -> None:
        """背景處理圖片生成"""
        logger.info(f"[{user_id}] Starting image generation for prompt: {prompt_chinese[:50]}...")
        try:
            # 翻譯提示詞
            prompt_english = self.ai_service.translate_prompt_for_image_generation(prompt_chinese)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=f"翻譯完成，專業指令為：「{prompt_english}」。\n正在請 AI 模型繪製...")]
                )
            )
            
            # 生成圖片
            image_data, gen_status = self.ai_service.generate_image(prompt_english)
            if image_data:
                # 上傳圖片
                image_url, upload_status = self.storage_service.upload_image_to_cloudinary(image_data)
                if image_url:
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[ImageMessage(original_content_url=image_url, preview_image_url=image_url)]
                        )
                    )
                    logger.info(f"[{user_id}] Image generated and sent successfully.")
                else:
                    line_bot_api.push_message(
                        PushMessageRequest(to=user_id, messages=[TextMessage(text=upload_status)])
                    )
                    logger.warning(f"[{user_id}] Image upload failed: {upload_status}")
            else:
                line_bot_api.push_message(
                    PushMessageRequest(to=user_id, messages=[TextMessage(text=gen_status)])
                )
                logger.warning(f"[{user_id}] Image generation failed: {gen_status}")
                
        except Exception as e:
            logger.error(f"[{user_id}] Image generation process failed: {e}", exc_info=True)
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="圖片生成過程中發生錯誤，請稍後再試。")])
            )
    
    def _handle_search_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
        """處理搜尋指令"""
        # Remove search prefixes from the message
        # Example: "搜尋 台北101" -> "台北101", "尋找 附近 咖啡" -> "附近 咖啡"
        search_query = message
        for prefix in self.SEARCH_COMMAND_PREFIXES:
            if search_query.startswith(prefix):
                search_query = search_query[len(prefix):].strip()
                break
        
        if not search_query:
            self._reply_error(line_bot_api, reply_token, "請提供搜尋關鍵字，例如：搜尋 台北101 或 搜尋 附近 餐廳")
            return

        if "附近" in search_query:
            # For "附近" searches, we need user's location. Store the query and ask for location.
            self._handle_nearby_search_prompt(line_bot_api, reply_token, user_id, search_query)
        else:
            # For direct location searches, proceed directly.
            self._handle_direct_location_search(line_bot_api, reply_token, user_id, search_query)
    
    def _handle_nearby_search_prompt(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, query: str) -> None:
        """處理需要用戶分享位置的附近搜尋指令"""
        # query example: "咖啡附近" or "附近咖啡"
        parts = query.split("附近")
        # Determine the actual keyword to search for, defaulting to "餐廳"
        # If "咖啡附近", parts=['咖啡', ''], keyword is '咖啡'
        # If "附近咖啡", parts=['', '咖啡'], keyword is '咖啡'
        # If "附近", parts=['', ''], keyword defaults to "餐廳"
        search_keyword = (parts[0].strip() or parts[1].strip()) if len(parts) > 1 else "餐廳"

        self.storage_service.set_nearby_query(user_id, search_keyword)
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，要搜尋您附近的「{search_keyword}」，請點擊左下角的「+」按鈕，分享您的位置給我喔！")]
            )
        )
    
    def _handle_direct_location_search(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, query: str) -> None:
        """處理直接地點搜尋指令"""
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"收到！正在為您搜尋「{query}」...")]
            )
        )
        
        # 在背景處理搜尋
        threading.Thread(
            target=self._process_location_search,
            args=(line_bot_api, user_id, query)
        ).start()
    
    def _process_location_search(self, line_bot_api: MessagingApi, user_id: str, query: str) -> None:
        """背景處理地點搜尋"""
        logger.info(f"[{user_id}] Starting location search for query: {query}")
        try:
            place_data = self.ai_service.search_location(query)
            self._create_location_carousel([place_data] if place_data else [], line_bot_api, user_id)
            logger.info(f"[{user_id}] Location search completed.")
            
        except Exception as e:
            logger.error(f"[{user_id}] Location search process failed: {e}", exc_info=True)
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="搜尋過程中發生錯誤，請稍後再試。")])
            )
    
    def _handle_chat_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
        """處理一般對話"""
        try:
            # 取得對話歷史
            history = self.storage_service.get_chat_history(user_id)
            
            # 與 AI 對話
            response_text, updated_history = self.ai_service.chat_with_history(message, history)
            
            # 儲存更新的歷史
            self.storage_service.save_chat_history(user_id, updated_history)
            
            # 回覆訊息
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=response_text)])
            )
            
        except Exception as e:
            logger.error(f"[{user_id}] Chat process failed: {e}", exc_info=True)
            self._reply_error(line_bot_api, reply_token, "對話處理時發生錯誤，請稍後再試。")


class ImageMessageHandler(MessageHandler):
    """圖片訊息處理器"""
    
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        """處理圖片訊息"""
        reply_token = event.reply_token
        message_id = event.message.id
        user_id = event.source.user_id
        
        if not self.ai_service.is_available():
            self._reply_error(line_bot_api, reply_token, "圖片分析功能未啟用")
            return
        
        try:
            # 回覆確認訊息
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="收到您的圖片了，正在進行分析...")]
                )
            )
            
            # 在背景處理圖片分析
            threading.Thread(
                target=self._process_image_analysis,
                args=(line_bot_api, user_id, message_id)
            ).start()
            
        except Exception as e:
            logger.error(f"[{user_id}] Image message handling failed: {e}", exc_info=True)
            self._reply_error(line_bot_api, reply_token, "圖片處理時發生錯誤")
    
    def _process_image_analysis(self, line_bot_api: MessagingApi, user_id: str, message_id: str) -> None:
        """背景處理圖片分析"""
        logger.info(f"[{user_id}] Starting image analysis for message_id: {message_id}")
        try:
            # 取得圖片內容
            line_bot_blob_api = MessagingApiBlob(line_bot_api.api_client)
            message_content = line_bot_blob_api.get_message_content(message_id)
            
            # 分析圖片
            analysis_result = self.ai_service.analyze_image(message_content)
            
            # 發送分析結果
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=f"圖片分析結果：\n{analysis_result}")]
                )
            )
            logger.info(f"[{user_id}] Image analysis completed.")
            
        except Exception as e:
            logger.error(f"[{user_id}] Image analysis process failed: {e}", exc_info=True)
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="圖片分析過程中發生錯誤，請稍後再試。")])
            )


class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""
    
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        """處理位置訊息"""
        reply_token = event.reply_token
        user_id = event.source.user_id
        latitude = event.message.latitude
        longitude = event.message.longitude
        
        # 取得搜尋關鍵字 (例如：使用者輸入"搜尋附近咖啡"後，分享位置)
        search_keyword = self.storage_service.get_nearby_query(user_id) or "餐廳"
        
        # 回覆確認訊息
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"收到您的位置！正在搜尋附近的「{search_keyword}」，請稍候...")]
            )
        )
        
        # 在背景處理附近搜尋
        threading.Thread(
            target=self._process_nearby_search,
            args=(line_bot_api, user_id, latitude, longitude, search_keyword)
        ).start()
    
    def _process_nearby_search(
        self, 
        line_bot_api: MessagingApi, 
        user_id: str, 
        latitude: float, 
        longitude: float, 
        keyword: str
    ) -> None:
        """背景處理附近搜尋"""
        logger.info(f"[{user_id}] Starting nearby search for keyword: {keyword} at ({latitude}, {longitude})")
        
        try:
            places = self.ai_service.search_nearby_locations(latitude, longitude, keyword)
            self._create_location_carousel(places or [], line_bot_api, user_id)
            
            logger.info(f"[{user_id}] Nearby search completed.")
            
        except Exception as e:
            logger.error(f"[{user_id}] Nearby search process failed: {e}", exc_info=True)
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="附近搜尋過程中發生錯誤，請稍後再試。")])
            )
