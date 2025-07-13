# app.py

import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent

from handlers.message_handlers import TextMessageHandler, ImageMessageHandler, LocationMessageHandler
from services.ai_service import AIService
from services.storage_service import StorageService
from utils.logger import get_logger, setup_root_logger

# 引入 Vertex AI 初始化工具
import vertexai

setup_root_logger()
logger = get_logger(__name__)

class LineBotApp:
    def __init__(self):
        logger.info("Initializing LINE Bot application...")

        # 【核心修正】在這裡直接初始化 Vertex AI
        # 它會自動讀取 GOOGLE_APPLICATION_CREDENTIALS 環境變數
        try:
            vertexai.init()
            logger.info("Vertex AI initialized successfully using Application Default Credentials.")
        except Exception as e:
            logger.error(f"Vertex AI initialization failed: {e}", exc_info=True)
            # 即使初始化失敗，也讓 app 繼續運行，但 AI 服務會不可用

        # 從環境變數直接讀取設定
        self.line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')
        self.line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
        # ... 其他服務的初始化 ...

        self.app = Flask(__name__)
        # ... (後續程式碼與之前版本類似)

def create_app() -> Flask:
    bot_app = LineBotApp()
    return bot_app.app