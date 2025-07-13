"""
主應用程式模組
整合所有服務和處理器
"""
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent

from config.settings import load_config
from config.render_settings import load_render_config
from services.ai_service import AIService
from services.storage_service import StorageService
from handlers.message_handlers import TextMessageHandler, ImageMessageHandler, LocationMessageHandler
from utils.logger import get_logger, setup_root_logger

# 設定根日誌記錄器
setup_root_logger()
logger = get_logger(__name__)


class LineBotApp:
    """LINE Bot 應用程式類別"""
    
    def __init__(self):
        # 根據環境選擇配置
        if os.getenv('RENDER'):
            self.config = load_render_config()
        else:
            self.config = load_config()
            
        self.app = Flask(__name__)
        
        # Render 平台優化
        if os.getenv('RENDER'):
            self._configure_for_render()
        
        # 初始化服務
        self.ai_service = AIService(self.config)
        self.storage_service = StorageService(self.config)
        
        # 初始化處理器
        self.text_handler = TextMessageHandler(self.ai_service, self.storage_service)
        self.image_handler = ImageMessageHandler(self.ai_service, self.storage_service)
        self.location_handler = LocationMessageHandler(self.ai_service, self.storage_service)
        
        # 初始化 LINE Bot
        self.handler = WebhookHandler(self.config.line_channel_secret)
        self.configuration = Configuration(access_token=self.config.line_channel_access_token)
        
        # 註冊路由和事件處理器
        self._register_routes()
        self._register_handlers()
        
        logger.info("LINE Bot application initialized successfully")
    
    def _configure_for_render(self) -> None:
        """Render 平台特定配置"""
        # 設定 Flask 配置
        self.app.config.update({
            'JSON_SORT_KEYS': False,
            'JSONIFY_PRETTYPRINT_REGULAR': False,
            'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # 1 年快取
        })
        
        # 添加健康檢查優化
        @self.app.before_request
        def before_request():
            # 跳過健康檢查的詳細處理
            if request.path in ['/health', '/']:
                return None
    
    def _register_routes(self) -> None:
        """註冊 Flask 路由"""
        
        @self.app.route("/")
        def home():
            return {
                "status": "running",
                "message": "AI LINE Bot is running successfully!",
                "services": {
                    "ai_service": self.ai_service.is_available(),
                    "redis_service": self.storage_service.is_redis_available()
                }
            }
        
        @self.app.route("/health")
        def health_check():
            """健康檢查端點"""
            return {
                "status": "healthy",
                "ai_service": self.ai_service.is_available(),
                "redis_service": self.storage_service.is_redis_available()
            }
        
        @self.app.route("/callback", methods=['POST'])
        def callback():
            """LINE Webhook 回調端點"""
            signature = request.headers.get('X-Line-Signature')
            if not signature:
                logger.warning("Missing X-Line-Signature header")
                abort(400)
            
            body = request.get_data(as_text=True)
            
            try:
                self.handler.handle(body, signature)
            except InvalidSignatureError:
                logger.error("Invalid signature")
                abort(400)
            except Exception as e:
                logger.error(f"Webhook handling error: {e}")
                abort(500)
            
            return 'OK'
    
    def _register_handlers(self) -> None:
        """註冊 LINE 事件處理器"""
        
        @self.handler.add(MessageEvent, message=TextMessageContent)
        def handle_text_message(event):
            """處理文字訊息事件"""
            try:
                api_client = ApiClient(self.configuration)
                line_bot_api = MessagingApi(api_client)
                self.text_handler.handle(event, line_bot_api)
                
            except Exception as e:
                logger.error(f"Text message handling error: {e}")
        
        @self.handler.add(MessageEvent, message=ImageMessageContent)
        def handle_image_message(event):
            """處理圖片訊息事件"""
            try:
                api_client = ApiClient(self.configuration)
                line_bot_api = MessagingApi(api_client)
                self.image_handler.handle(event, line_bot_api)
                
            except Exception as e:
                logger.error(f"Image message handling error: {e}")
        
        @self.handler.add(MessageEvent, message=LocationMessageContent)
        def handle_location_message(event):
            """處理位置訊息事件"""
            try:
                api_client = ApiClient(self.configuration)
                line_bot_api = MessagingApi(api_client)
                self.location_handler.handle(event, line_bot_api)
                
            except Exception as e:
                logger.error(f"Location message handling error: {e}")
    
    def run(self) -> None:
        """啟動應用程式"""
        if self.config.debug:
            logger.info(f"Starting Flask development server on port {self.config.port}")
            self.app.run(host="0.0.0.0", port=self.config.port, debug=True)
        else:
            logger.info(f"Starting production server on port {self.config.port}")
            from waitress import serve
            serve(self.app, host="0.0.0.0", port=self.config.port)


def create_app() -> Flask:
    """建立 Flask 應用程式實例（用於部署）"""
    bot_app = LineBotApp()
    return bot_app.app


if __name__ == "__main__":
    try:
        bot_app = LineBotApp()
        bot_app.run()
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise