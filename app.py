# app.py

"""
主應用程式模組
整合所有服務和處理器，並作為應用程式的統一入口點。
"""

import os
import sys
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent

# 依賴您專案中的其他模組
from config.settings import load_config
from handlers.message_handlers import TextMessageHandler, ImageMessageHandler, LocationMessageHandler
from services.ai_service import AIService
from services.storage_service import StorageService
from utils.logger import get_logger, setup_root_logger

# 引入 Vertex AI 初始化工具
import vertexai
import json
from google.oauth2 import service_account


# 設定根日誌記錄器
setup_root_logger()
logger = get_logger(__name__)


class LineBotApp:
    """LINE Bot 應用程式類別"""

    def __init__(self):
        logger.info("Initializing LINE Bot application...")

        # 簡化設定載入流程
        self.config = load_config()
        logger.info("Application configuration loaded successfully.")

        # 在這裡直接初始化 Vertex AI
        self._initialize_vertex_ai()
        
        self.app = Flask(__name__)

        # 初始化核心服務
        self.ai_service = AIService(self.config)
        self.storage_service = StorageService(self.config)
        logger.debug("AI and Storage Services initialized.")

        # 初始化 LINE Bot API 客戶端
        self.configuration = Configuration(access_token=self.config.line_channel_access_token)
        self.api_client = ApiClient(self.configuration)
        self.line_bot_api = MessagingApi(self.api_client)
        logger.debug("LINE Bot API client initialized.")

        # 初始化訊息處理器和 Webhook
        self.text_handler = TextMessageHandler(self.ai_service, self.storage_service)
        self.image_handler = ImageMessageHandler(self.ai_service, self.storage_service)
        self.location_handler = LocationMessageHandler(self.ai_service, self.storage_service)
        self.handler = WebhookHandler(self.config.line_channel_secret)
        logger.debug("Message handlers and Webhook handler initialized.")
        
        self._register_routes()
        self._register_handlers()
        logger.info("LINE Bot application initialization complete.")

    def _initialize_vertex_ai(self):
        """使用環境變數中的 JSON 字串來初始化 Vertex AI"""
        try:
            gcp_json_str = self.config.gcp_service_account_json
            credentials_info = json.loads(gcp_json_str)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            vertexai.init(project=self.config.gcp_project_id, location=self.config.gcp_location, credentials=credentials)
            logger.info("Vertex AI initialized successfully.")
        except Exception as e:
            logger.error(f"Vertex AI initialization failed: {e}", exc_info=True)
            
    def _register_routes(self):
        """註冊 Flask 路由"""
        @self.app.route("/")
        def home():
            return {"status": "running"}

        @self.app.route("/callback", methods=['POST'])
        def callback():
            signature = request.headers.get('X-Line-Signature')
            if not signature: abort(400)
            body = request.get_data(as_text=True)
            try:
                self.handler.handle(body, signature)
            except InvalidSignatureError:
                abort(400)
            except Exception:
                logger.exception("Error processing webhook")
                abort(500)
            return 'OK'

    def _register_handlers(self):
        """註冊 LINE 事件處理器"""
        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text(event):
            self.text_handler.handle(event, self.line_bot_api)

        @self.handler.add(MessageEvent, message=ImageMessageContent)
        def handle_image(event):
            self.image_handler.handle(event, self.line_bot_api)

        @self.handler.add(MessageEvent, message=LocationMessageContent)
        def handle_location(event):
            self.location_handler.handle(event, self.line_bot_api)

# --- 工廠函式與主程式入口 ---

def create_app() -> Flask:
    """建立 Flask 應用程式實例 (供 Gunicorn 使用)"""
    logger.info("create_app() called by WSGI server.")
    bot_app = LineBotApp()
    return bot_app.app

# 【核心修正】將原本 main.py 的啟動邏輯整合進來，並確保有內容
if __name__ == "__main__":
    try:
        logger.info("Running app.py directly. This is for local development.")
        bot_app = LineBotApp()
        port = bot_app.config.port
        debug_mode = bot_app.config.debug
        
        if debug_mode:
            bot_app.app.run(host="0.0.0.0", port=port, debug=True)
        else:
            from waitress import serve
            serve(bot_app.app, host="0.0.0.0", port=port)

    except Exception:
        logger.critical("Application startup failed critically.", exc_info=True)
        sys.exit(1)