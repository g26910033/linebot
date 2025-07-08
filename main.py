# === 最終完美運行版 main.py ===

import os
import io
# 引入 Vertex AI 函式庫
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part, Content
# 引入專門的圖片生成模型函式庫
from vertexai.preview.vision_models import ImageGenerationModel

# 其他必要的函式庫
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    PushMessageRequest, ReplyMessageRequest,
    TextMessage, ImageMessage, MessagingApiBlob
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from replit import db # 注意：在 Render 上我們需要用其他方式取代 replit.db
import cloudinary
import cloudinary.uploader

# --- 初始化設定 ---

app = Flask(__name__)

# 從 Render 的環境變數中讀取我們的金鑰
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID')
GCP_LOCATION = os.getenv('GCP_LOCATION')
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

# 由於 Render 沒有內建 replit.db，我們用一個簡單的字典來暫存記憶
# 若需要永久記憶，未來可升級至 Redis 或其他資料庫
user_sessions = {}
long_term_memory = {}


# 使用服務帳戶金鑰初始化 Vertex AI
# 在 Render 上，我們需要設定 GOOGLE_APPLICATION_CREDENTIALS
try:
    # Render 會自動偵測 GOOGLE_APPLICATION_CREDENTIALS
    vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
    text_vision_model = GenerativeModel("gemini-1.5-pro-latest")
    image_gen_model = ImageGenerationModel.from_pretrained("imagegeneration@006")
    print("Vertex AI initialized successfully.")
except Exception as e:
    print(f"Vertex AI initialization failed: {e}")
    text_vision_model = None
    image_gen_model = None

# 設定 Cloudinary
if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    cloudinary.config(cloud_name=CLOUDINARY_CLOUD_NAME, api_key=CLOUDINARY_API_KEY, api_secret=CLOUDINARY_API_SECRET)

# 設定 LINE Bot
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# ... (後續的功能函式與核心邏輯) ...