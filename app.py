# app.py

"""
主應用程式模組
整合所有服務和處理器，並作為應用程式的統一入口點。
"""

import sys
import json
import os
import requests
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

        self.configuration = Configuration(
            access_token=self.config.line_channel_access_token)

        services = self._initialize_services()
        logger.debug("All services initialized.")

        # 修正：將 text_handler 傳遞給 image_handler 和 location_handler
        self.text_handler = TextMessageHandler(services, self.configuration)
        self.image_handler = ImageMessageHandler(
            self.configuration, services['storage'], self.text_handler)
        self.location_handler = LocationMessageHandler(
            self.configuration, services['storage'], self.text_handler)

        self.handler = WebhookHandler(self.config.line_channel_secret)
        logger.debug("Message handlers and Webhook handler initialized.")

        self._register_routes()
        self._register_handlers()

        logger.info("LINE Bot application initialization complete.")

    def _initialize_services(self) -> dict:
        core_service = AICoreService(self.config)
        storage_service = StorageService(self.config)
        
        # 初始化圖片服務並注入儲存服務以啟用快取
        image_service = AIImageService(self.config, core_service)
        image_service.set_storage_service(storage_service)
        
        # 初始化背景任務管理器
        try:
            from services.background_tasks import BackgroundTaskManager
            background_task_manager = BackgroundTaskManager(storage_service)
            logger.info("Background task manager initialized.")
        except Exception as e:
            logger.warning(f"Background task manager initialization failed: {e}")
            background_task_manager = None
        
        stock_service = None
        if self.config.finnhub_api_key:
            stock_service = StockService(self.config.finnhub_api_key)
            logger.debug("Stock Service initialized.")
        else:
            logger.warning("FINNHUB_API_KEY not set. Stock service is disabled.")

        web_service = WebService()
        return {
            "core": core_service,
            "parsing": AIParsingService(self.config, core_service),
            "image": image_service,
            "text": AITextService(self.config, core_service, web_service),
            "storage": storage_service,
            "web": web_service,
            "weather": WeatherService(self.config.openweather_api_key),
            "news": NewsService(self.config.news_api_key),
            "calendar": CalendarService(),
            "stock": stock_service,
            "background_tasks": background_task_manager
        }

    def _initialize_vertex_ai(self):
        try:
            gcp_json_str = self.config.gcp_service_account_json
            credentials_info = json.loads(gcp_json_str)
            credentials = service_account.Credentials.from_service_account_info(credentials_info)
            vertexai.init(project=self.config.gcp_project_id, location=self.config.gcp_location, credentials=credentials)
            logger.info("Vertex AI initialized successfully.")
        except Exception as e:
            logger.error(f"Vertex AI initialization failed: {e}", exc_info=True)

    def _setup_default_rich_menu(self):
        """檢查並設定預設的圖文選單，會強制刪除舊的同名選單"""
        rich_menu_name = "Default Rich Menu"
        headers = {"Authorization": f"Bearer {self.config.line_channel_access_token}"}
        
        try:
            response = requests.get("https://api.line.me/v2/bot/richmenu/list", headers=headers, timeout=5)
            response.raise_for_status()
            existing_menus = response.json().get('richmenus', [])
            for menu in existing_menus:
                if menu.get('name') == rich_menu_name:
                    delete_url = f"https://api.line.me/v2/bot/richmenu/{menu['richMenuId']}"
                    delete_response = requests.delete(delete_url, headers=headers)
                    if delete_response.status_code == 200:
                        logger.info(f"Deleted old rich menu with ID: {menu['richMenuId']}")
                    else:
                        logger.warning(f"Failed to delete old rich menu {menu['richMenuId']}: {delete_response.text}")
        except requests.RequestException as e:
            logger.error(f"Failed to get or delete rich menu list: {e}")

        logger.info(f"Proceeding to create new rich menu '{rich_menu_name}'...")
        
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, 'scripts', 'rich_menu.json')
            with open(json_path, 'r', encoding='utf-8') as f:
                rich_menu_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"{json_path} not found. Cannot set up rich menu.")
            return
            
        rich_menu_data['name'] = rich_menu_name
        
        response = requests.post(
            "https://api.line.me/v2/bot/richmenu",
            headers={**headers, "Content-Type": "application/json"},
            data=json.dumps(rich_menu_data)
        )
        if response.status_code != 200:
            logger.error(f"Error creating rich menu: {response.status_code} {response.text}")
            return
        rich_menu_id = response.json()['richMenuId']
        logger.info(f"Rich menu created successfully. ID: {rich_menu_id}")

        try:
            png_path = os.path.join(base_dir, 'scripts', 'rich_menu_background.png')
            with open(png_path, 'rb') as f:
                image_data = f.read()
        except FileNotFoundError:
            logger.error(f"{png_path} not found. Cannot upload image.")
            return
            
        upload_response = requests.post(
            f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
            headers={**headers, "Content-Type": "image/png"},
            data=image_data
        )
        if upload_response.status_code != 200:
            logger.error(f"Error uploading rich menu image: {upload_response.status_code} {upload_response.text}")
            return
        logger.info("Rich menu image uploaded successfully.")

        default_response = requests.post(
            f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
            headers=headers
        )
        if default_response.status_code != 200:
            logger.error(f"Error setting default rich menu: {default_response.status_code} {default_response.text}")
            return
        logger.info("Rich menu set as default successfully.")

    def _register_routes(self):
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
            self.text_handler.handle_postback(event)

def create_app() -> Flask:
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
