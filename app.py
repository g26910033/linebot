# app.py

"""
主應用程式模組
整合所有服務和處理器，並作為應用程式的統一入口點。
"""

import sys
import json
import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, RichMenuRequest,
    ApiException)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, ImageMessageContent,
    LocationMessageContent, PostbackEvent)

# 依賴您專案中的其他模組
from config.settings import load_config
from handlers.message_handlers import (
    TextMessageHandler, ImageMessageHandler, LocationMessageHandler)
from services.ai.core import AICoreService
from services.ai.parsing_service import AIParsingService
from services.ai.image_service import AIImageService
from services.ai.text_service import AITextService
from services.web_service import WebService
from services.storage_service import StorageService
from services.weather_service import WeatherService
from services.news_service import NewsService
from services.calendar_service import CalendarService
from services.stock_service import StockService
from utils.logger import get_logger, setup_root_logger

# 引入 Vertex AI 初始化工具
import vertexai
from google.oauth2 import service_account


# 設定根日誌記錄器
setup_root_logger()
logger = get_logger(__name__)


class LineBotApp:
    """LINE Bot 應用程式類別"""

    def __init__(self):
        logger.info("Initializing LINE Bot application...")
        self.config = load_config()
        logger.info("Application configuration loaded successfully.")
        self._initialize_vertex_ai()
        self.app = Flask(__name__)

        # 建立一個共用的 Configuration 物件
        self.configuration = Configuration(
            access_token=self.config.line_channel_access_token)

        # 將所有服務打包成一個字典
        services = self._initialize_services()
        logger.debug("All services initialized.")

        # 初始化訊息處理器和 Webhook
        # 注意：我們不再傳遞一個全域的 line_bot_api 物件
        self.text_handler = TextMessageHandler(services, self.configuration)
        self.image_handler = ImageMessageHandler(
            self.configuration, services['storage'])
        self.location_handler = LocationMessageHandler(
            self.configuration, services['storage'])

        self.handler = WebhookHandler(self.config.line_channel_secret)
        logger.debug("Message handlers and Webhook handler initialized.")

        self._register_routes()
        self._register_handlers()

        logger.info("LINE Bot application initialization complete.")

    def _initialize_services(self) -> dict:
        """初始化所有服務並返回一個字典。"""
        core_service = AICoreService(self.config)
        stock_service = None
        if self.config.finnhub_api_key:
            stock_service = StockService(self.config.finnhub_api_key)
            logger.debug("Stock Service initialized.")
        else:
            logger.warning(
                "FINNHUB_API_KEY not set. Stock service is disabled.")

        return {
            "core": core_service,
            "parsing": AIParsingService(self.config, core_service),
            "image": AIImageService(self.config, core_service),
            "text": AITextService(self.config, core_service),
            "storage": StorageService(self.config),
            "web": WebService(),
            "weather": WeatherService(self.config.openweather_api_key),
            "news": NewsService(self.config.news_api_key),
            "calendar": CalendarService(),
            "stock": stock_service
        }

    def _initialize_vertex_ai(self):
        """使用環境變數中的 JSON 字串來初始化 Vertex AI"""
        try:
            gcp_json_str = self.config.gcp_service_account_json
            credentials_info = json.loads(gcp_json_str)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info)
            vertexai.init(
                project=self.config.gcp_project_id,
                location=self.config.gcp_location,
                credentials=credentials)
            logger.info("Vertex AI initialized successfully.")
        except Exception as e:
            logger.error(
                f"Vertex AI initialization failed: {e}",
                exc_info=True)

    def _setup_default_rich_menu(self):
        """使用 line-bot-sdk 檢查並設定預設的圖文選單。"""
        rich_menu_name = "Default Rich Menu"
        logger.info("--- Starting Rich Menu Setup ---")
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, 'scripts', 'rich_menu.json')
            png_path = os.path.join(
                base_dir, 'scripts', 'rich_menu_background.png')
            if not os.path.exists(json_path) or not os.path.exists(png_path):
                logger.error("Rich menu files not found. Aborting setup.")
                return

            # 使用 'with' 陳述式來確保資源被正確管理
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)

                # Step 1: Delete Old Menus
                logger.info("Step 1: Deleting old rich menus...")
                rich_menu_list = line_bot_api.get_rich_menu_list()
                for menu in rich_menu_list.richmenus:
                    if menu.name == rich_menu_name:
                        logger.info(f"Deleting old menu: {menu.rich_menu_id}")
                        line_bot_api.delete_rich_menu(menu.rich_menu_id)
                logger.info("Step 1 finished.")

                # Step 2: Create New Menu
                logger.info("Step 2: Creating new rich menu...")
                with open(json_path, 'r', encoding='utf-8') as f:
                    rich_menu_json = json.load(f)
                rich_menu_json['name'] = rich_menu_name
                rich_menu_to_create = RichMenuRequest.from_dict(rich_menu_json)
                rich_menu_id_response = line_bot_api.create_rich_menu(
                    rich_menu_request=rich_menu_to_create)
                rich_menu_id = rich_menu_id_response.rich_menu_id
                logger.info(f"Step 2 finished. New menu ID: {rich_menu_id}")

                # Step 3: Upload Image
                logger.info(f"Step 3: Uploading image for menu ID: {rich_menu_id}")
                with open(png_path, 'rb') as f:
                    line_bot_api.upload_rich_menu_image(
                        rich_menu_id=rich_menu_id,
                        body=f.read(),
                        _headers={'Content-Type': 'image/png'}
                    )
                logger.info("Step 3 finished. Image uploaded.")

                # Step 4: Set as Default
                logger.info(f"Step 4: Setting menu {rich_menu_id} as default...")
                line_bot_api.set_default_rich_menu(rich_menu_id)
                logger.info("Step 4 finished. Menu set as default.")

        except ApiException as e:
            logger.error(f"LINE API Error during rich menu setup: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"An unexpected error occurred during rich menu setup: {e}", exc_info=True)

    def _register_routes(self):
        """註冊 Flask 路由"""
        @self.app.route("/")
        def home():
            return {"status": "running"}

        @self.app.route("/callback", methods=['POST'])
        def callback():
            signature = request.headers.get('X-Line-Signature')
            if not signature:
                abort(400)
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
            self.text_handler.handle(event)

        @self.handler.add(MessageEvent, message=ImageMessageContent)
        def handle_image(event):
            self.image_handler.handle(event)

        @self.handler.add(MessageEvent, message=LocationMessageContent)
        def handle_location(event):
            self.location_handler.handle(event)

        @self.handler.add(PostbackEvent)
        def handle_postback(event):
            self.text_handler.handle(event)


def create_app() -> Flask:
    """建立 Flask 應用程式實例 (供 Gunicorn 使用)"""
    logger.info("create_app() called by WSGI server.")
    bot_app = LineBotApp()
    bot_app._setup_default_rich_menu()
    return bot_app.app


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
