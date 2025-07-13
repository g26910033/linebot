"""
主應用程式模組
整合所有服務和處理器
"""
import os
import sys # 用於在應用程式啟動失敗時退出程序

from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent

from config.settings import load_config
from config.render_settings import load_render_config
from handlers.message_handlers import TextMessageHandler, ImageMessageHandler, LocationMessageHandler
from services.ai_service import AIService
from services.storage_service import StorageService
from utils.logger import get_logger, setup_root_logger

# 設定根日誌記錄器
setup_root_logger()
logger = get_logger(__name__)


class LineBotApp:
    """LINE Bot 應用程式類別
    負責初始化 Flask 應用程式、LINE Bot 客戶端、服務和訊息處理器。
    它協調所有組件以處理來自 LINE 的 Webhook 事件。
    """

    def __init__(self):
        logger.info("Initializing LINE Bot application...")

        # 根據環境變數 'RENDER' 選擇應用程式配置
        # Render 平台通常會設定 RENDER 環境變數為 'true'
        if os.getenv('RENDER') == 'true':
            self.config = load_render_config()
            logger.info("Loaded Render platform-specific configuration.")
        else:
            self.config = load_config()
            logger.info("Loaded default application configuration.")

        self.app = Flask(__name__)

        # 如果在 Render 平台上運行，應用額外的 Flask 配置優化
        if os.getenv('RENDER') == 'true':
            self._configure_for_render()

        # 初始化核心服務，這些服務將被訊息處理器利用
        self.ai_service: AIService = AIService(self.config)
        self.storage_service: StorageService = StorageService(self.config)
        logger.debug("AI Service and Storage Service initialized.")

        # 初始化 LINE Bot API 客戶端
        # Configuration 和 ApiClient 應為單例，以優化資源使用和連線管理
        self.configuration: Configuration = Configuration(access_token=self.config.line_channel_access_token)
        self.api_client: ApiClient = ApiClient(self.configuration) # ApiClient 負責 HTTP 連線
        self.line_bot_api: MessagingApi = MessagingApi(self.api_client) # MessagingApi 提供方便的 API 呼叫方法
        logger.debug("LINE Bot API client initialized.")

        # 初始化各類型訊息處理器，每個處理器負責處理特定類型的 LINE 訊息
        self.text_handler: TextMessageHandler = TextMessageHandler(self.ai_service, self.storage_service)
        self.image_handler: ImageMessageHandler = ImageMessageHandler(self.ai_service, self.storage_service)
        self.location_handler: LocationMessageHandler = LocationMessageHandler(self.ai_service, self.storage_service)
        logger.debug("Message handlers initialized.")

        # 初始化 LINE Bot Webhook 處理器，用於驗證傳入請求的簽章並分發事件
        self.handler: WebhookHandler = WebhookHandler(self.config.line_channel_secret)
        logger.debug("LINE Webhook handler initialized.")

        # 註冊 Flask 路由和 LINE 事件處理器，將請求和事件導向對應的邏輯
        self._register_routes()
        self._register_handlers()
        logger.info("Flask routes and LINE event handlers registered.")

        logger.info("LINE Bot application initialization complete.")

    def _configure_for_render(self) -> None:
        """Render 平台特定配置與優化。
        設定 Flask 應用程式配置以適應 Render 環境，並添加健康檢查優化。
        這有助於提高性能和資源利用率。
        """
        logger.info("Applying Render-specific Flask configurations...")
        # 設定 Flask 配置，優化 JSON 響應和靜態檔案快取
        self.app.config.update({
            'JSON_SORT_KEYS': False,  # 禁用 JSON 鍵排序，減少 CPU 開銷，提高響應速度
            'JSONIFY_PRETTYPRINT_REGULAR': False,  # 禁用 JSON 響應美化，減少輸出大小和網路傳輸
            'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # 設定靜態檔案的快取時間為一年 (秒)，減少瀏覽器重複請求
        })
        logger.debug("Flask app config updated: JSON sorting disabled, pretty print disabled, static file max age set.")

        # 添加健康檢查優化：對於健康檢查路徑，直接跳過不必要的請求前處理
        # 避免在每次健康檢查請求時執行所有 before_request 函式，減少開銷
        @self.app.before_request
        def before_request_optimization() -> None:
            """在處理請求前執行優化。對於 '/health' 和 '/' 路徑，跳過不必要的處理。"""
            if request.path in ['/health', '/']:
                logger.debug(f"Skipping extensive before_request processing for path: {request.path}")
                # 返回 None 允許 Flask 繼續處理請求，但不執行後續的 before_request 函式
                # (如果有多個的話，此處邏輯需配合整體 before_request 設計)
                # 在本例中，主要目的是避免不必要的副作用或資源消耗。
                return None

    def _register_routes(self) -> None:
        """註冊 Flask 路由，包括根路徑、健康檢查和 LINE Webhook 回調。"""
        logger.debug("Registering Flask routes: /, /health, /callback.")

        @self.app.route("/")
        def home() -> dict:
            """根路徑端點，提供應用程式的基本運行狀態。
            可用於快速檢查服務是否線上。
            """
            # 檢查服務可用性，這會涉及對 AI 服務和 Redis 的輕量級檢查
            ai_available = self.ai_service.is_available()
            redis_available = self.storage_service.is_redis_available()
            logger.info(f"Home route accessed. Services status: AI={ai_available}, Redis={redis_available}.")
            return {
                "status": "running",
                "message": "AI LINE Bot is running successfully!",
                "services": {
                    "ai_service": ai_available,
                    "redis_service": redis_available
                }
            }

        @self.app.route("/health")
        def health_check() -> dict:
            """健康檢查端點。
            此端點應快速響應，僅檢查關鍵服務的即時狀態，不執行複雜邏輯。
            """
            ai_available = self.ai_service.is_available()
            redis_available = self.storage_service.is_redis_available()
            logger.debug(f"Health check accessed. Services status: AI={ai_available}, Redis={redis_available}.")
            return {
                "status": "healthy",
                "ai_service": ai_available,
                "redis_service": redis_available
            }

        @self.app.route("/callback", methods=['POST'])
        def callback() -> str:
            """LINE Webhook 回調端點。
            處理來自 LINE 的所有訊息和事件。這是 LINE Bot 的主要入口點。
            """
            signature = request.headers.get('X-Line-Signature')
            if not signature:
                logger.warning("Missing 'X-Line-Signature' header. This request might not be from LINE. Aborting with 400.")
                abort(400, description="Missing 'X-Line-Signature' header.")

            body = request.get_data(as_text=True)
            logger.debug(f"Received LINE webhook callback. Body length: {len(body)} bytes.")

            try:
                # WebhookHandler 負責驗證簽章的有效性，並解析請求體為 LINE 事件對象
                self.handler.handle(body, signature)
                logger.info("LINE webhook callback processed successfully.")
            except InvalidSignatureError:
                # 當簽章無效時，通常表示請求來源不可信或簽章密鑰不匹配
                logger.error("Invalid signature received from LINE webhook. Request likely forged or misconfigured. Aborting with 400.")
                abort(400, description="Invalid signature.")
            except Exception as e:
                # 捕獲處理 Webhook 時可能發生的所有其他異常
                logger.exception(f"An unexpected error occurred during LINE webhook handling: {e}") # 使用 logger.exception 記錄完整的堆棧追蹤
                abort(500, description="Internal server error during webhook processing.")

            return 'OK'

    def _register_handlers(self) -> None:
        """註冊 LINE 事件處理器，根據訊息類型分發到對應的處理器。
        這些處理器負責將 LINE 事件轉化為業務邏輯。
        """
        logger.debug("Registering LINE event handlers for Text, Image, and Location messages.")

        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text_message(event: MessageEvent) -> None:
            """處理文字訊息事件。"""
            user_id = event.source.user_id if event.source else 'unknown_user'
            logger.info(f"Handling TextMessage from user: {user_id}. Message: '{event.message.text[:50]}...' وصلت")
            try:
                # 將事件和 LINE API 客戶端傳遞給文字訊息處理器進行進一步處理
                self.text_handler.handle(event, self.line_bot_api)
                logger.debug(f"TextMessage for user {user_id} processed successfully.")
            except Exception as e:
                logger.exception(f"Error handling TextMessage for user {user_id}: {e}") # 記錄詳細錯誤和堆棧追蹤

        @self.handler.add(MessageEvent, message=ImageMessageContent)
        def handle_image_message(event: MessageEvent) -> None:
            """處理圖片訊息事件。"""
            user_id = event.source.user_id if event.source else 'unknown_user'
            logger.info(f"Handling ImageMessage from user: {user_id}. Message ID: {event.message.id}")
            try:
                # 將事件和 LINE API 客戶端傳遞給圖片訊息處理器
                self.image_handler.handle(event, self.line_bot_api)
                logger.debug(f"ImageMessage for user {user_id} processed successfully.")
            except Exception as e:
                logger.exception(f"Error handling ImageMessage for user {user_id}: {e}")

        @self.handler.add(MessageEvent, message=LocationMessageContent)
        def handle_location_message(event: MessageEvent) -> None:
            """處理位置訊息事件。"""
            user_id = event.source.user_id if event.source else 'unknown_user'
            location_info = f"lat: {event.message.latitude}, lon: {event.message.longitude}"
            logger.info(f"Handling LocationMessage from user: {user_id}. Location: {location_info}")
            try:
                # 將事件和 LINE API 客戶端傳遞給位置訊息處理器
                self.location_handler.handle(event, self.line_bot_api)
                logger.debug(f"LocationMessage for user {user_id} processed successfully.")
            except Exception as e:
                logger.exception(f"Error handling LocationMessage for user {user_id}: {e}")

    def run(self) -> None:
        """啟動 Flask 應用程式。
        在開發模式下使用 Flask 內建伺服器，生產環境下使用 Waitress WSGI 伺服器。
        """
        port = self.config.port
        host = "0.0.0.0" # 監聽所有可用的網路介面

        if self.config.debug:
            logger.info(f"Starting Flask development server on {host}:{port} (debug mode enabled).")
            # debug=True 會啟用 Flask 的調試器和重新載入器，僅適用於開發環境
            self.app.run(host=host, port=port, debug=True)
        else:
            logger.info(f"Starting production WSGI server (Waitress) on {host}:{port}.")
            # Waitress 是一個簡單且可靠的 WSGI 伺服器，適合小型到中型應用程式的生產部署
            from waitress import serve
            serve(self.app, host=host, port=port, _quiet=True) # _quiet=True 抑制 Waitress 的啟動信息，使日誌更簡潔

def create_app() -> Flask:
    """建立 Flask 應用程式實例。
    此函數通常由 WSGI 伺服器 (如 Gunicorn/Waitress) 調用，作為應用程式的入口點。
    每個 WSGI worker 通常會調用此函數一次來獲取應用程式實例。
    """
    logger.info("create_app() called. Instantiating LineBotApp for WSGI server.")
    bot_app = LineBotApp()
    return bot_app.app


if __name__ == "__main__":
    # 當直接運行此腳本時，啟動應用程式
    try:
        logger.info("Running app.py directly as the main script. Initiating application startup sequence.")
        bot_app = LineBotApp()
        bot_app.run()
    except Exception as e:
        # 捕獲並記錄應用程式啟動時的任何嚴重錯誤
        logger.critical(f"Application startup failed critically: {e}", exc_info=True)
        sys.exit(1) # 以非零退出碼結束程序，表示啟動失敗