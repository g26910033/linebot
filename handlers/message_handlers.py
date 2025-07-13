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


class TextMessageHandler(MessageHandler):
    """文字訊息處理器"""
    
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
        clear_keywords = ["清除對話", "忘記對話", "清除記憶"]
        return message.lower() in [keyword.lower() for keyword in clear_keywords]
    
    def _is_draw_command(self, message: str) -> bool:
        """檢查是否為繪圖指令"""
        return message.startswith("畫")
    
    def _is_search_command(self, message: str) -> bool:
        """檢查是否為搜尋指令"""
        search_keywords = ["搜尋", "尋找"]
        return any(message.startswith(keyword) for keyword in search_keywords)
    
    def _handle_clear_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str) -> None:
        """處理清除對話指令"""
        success = self.storage_service.clear_chat_history(user_id)
        message = "好的，我已經將我們先前的對話紀錄都忘記了。" if success else "清除對話記錄時發生錯誤。"
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=message)])
        )
    
    def _handle_draw_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
        """處理繪圖指令"""
        prompt_chinese = message.split("畫", 1)[1].strip()
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
                else:
                    line_bot_api.push_message(
                        PushMessageRequest(to=user_id, messages=[TextMessage(text=upload_status)])
                    )
            else:
                line_bot_api.push_message(
                    PushMessageRequest(to=user_id, messages=[TextMessage(text=gen_status)])
                )
                
        except Exception as e:
            logger.error(f"Image generation process failed: {e}")
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="圖片生成過程中發生錯誤，請稍後再試。")])
            )
    
    def _handle_search_command(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, message: str) -> None:
        """處理搜尋指令"""
        query = message.replace("搜尋", "").replace("尋找", "").strip()
        
        if "附近" in query:
            self._handle_nearby_search(line_bot_api, reply_token, user_id, query)
        else:
            self._handle_location_search(line_bot_api, reply_token, user_id, query)
    
    def _handle_nearby_search(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, query: str) -> None:
        """處理附近搜尋"""
        parts = query.split("附近")
        search_keyword = (parts[0].strip() or parts[1].strip()) or "餐廳"
        
        self.storage_service.set_nearby_query(user_id, search_keyword)
        
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=f"好的，要搜尋您附近的「{search_keyword}」，請點擊左下角的「+」按鈕，分享您的位置給我喔！")]
            )
        )
    
    def _handle_location_search(self, line_bot_api: MessagingApi, reply_token: str, user_id: str, query: str) -> None:
        """處理地點搜尋"""
        if not query:
            self._reply_error(line_bot_api, reply_token, "請提供搜尋關鍵字，例如：搜尋 台北101")
            return
        
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
        try:
            place_data = self.ai_service.search_location(query)
            self._create_location_carousel([place_data] if place_data else [], line_bot_api, user_id)
            
        except Exception as e:
            logger.error(f"Location search process failed: {e}")
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
            logger.error(f"Chat process failed: {e}")
            self._reply_error(line_bot_api, reply_token, "對話處理時發生錯誤，請稍後再試。")
    
    def _create_location_carousel(self, places_list: List[Dict[str, str]], line_bot_api: MessagingApi, user_id: str) -> None:
        """建立地點輪播訊息"""
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
                continue
            
            encoded_query = quote_plus(f"{place_name} {place_address}")
            map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            display_text = f"{place_address}\n電話：{phone_number}"
            
            column = CarouselColumn(
                title=place_name,
                text=display_text[:60],  # LINE 限制文字長度
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
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，AI 回傳的資料格式有誤，無法為您顯示地點。")])
            )
    
    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        """回覆錯誤訊息"""
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
        )


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
            logger.error(f"Image message handling failed: {e}")
            self._reply_error(line_bot_api, reply_token, "圖片處理時發生錯誤")
    
    def _process_image_analysis(self, line_bot_api: MessagingApi, user_id: str, message_id: str) -> None:
        """背景處理圖片分析"""
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
            
        except Exception as e:
            logger.error(f"Image analysis process failed: {e}")
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="圖片分析過程中發生錯誤，請稍後再試。")])
            )
    
    def _reply_error(self, line_bot_api: MessagingApi, reply_token: str, error_message: str) -> None:
        """回覆錯誤訊息"""
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=error_message)])
        )


class LocationMessageHandler(MessageHandler):
    """位置訊息處理器"""
    
    def handle(self, event: MessageEvent, line_bot_api: MessagingApi) -> None:
        """處理位置訊息"""
        reply_token = event.reply_token
        user_id = event.source.user_id
        latitude = event.message.latitude
        longitude = event.message.longitude
        
        # 取得搜尋關鍵字
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
        try:
            logger.info(f"Starting nearby search for user {user_id}, keyword: {keyword}")
            
            places = self.ai_service.search_nearby_locations(latitude, longitude, keyword)
            self._create_location_carousel(places or [], line_bot_api, user_id)
            
            logger.info(f"Nearby search completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Nearby search process failed: {e}")
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="附近搜尋過程中發生錯誤，請稍後再試。")])
            )
    
    def _create_location_carousel(self, places_list: List[Dict[str, str]], line_bot_api: MessagingApi, user_id: str) -> None:
        """建立地點輪播訊息"""
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
                continue
            
            encoded_query = quote_plus(f"{place_name} {place_address}")
            map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
            
            display_text = f"{place_address}\n電話：{phone_number}"
            
            column = CarouselColumn(
                title=place_name,
                text=display_text[:60],  # LINE 限制文字長度
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
            line_bot_api.push_message(
                PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，AI 回傳的資料格式有誤，無法為您顯示地點。")])
            )