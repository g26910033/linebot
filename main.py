# === 向下相容最終畢業版 main.py ===

import os
import io
import json
import redis

# 引入 Vertex AI 和 Google Auth 函式庫
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Part, Content
from vertexai.preview.vision_models import ImageGenerationModel
from google.oauth2 import service_account

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
import cloudinary
import cloudinary.uploader

# --- 初始化設定 ---

app = Flask(__name__)

# 從 Render 的環境變數中讀取我們的金鑰
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
GCP_SERVICE_ACCOUNT_JSON_STR = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
REDIS_URL = os.getenv('REDIS_URL')

# 初始化 Redis 連線
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True) # decode_responses=True 讓 Redis 回傳字串
        print("Redis client connected successfully.")
    except Exception as e:
        print(f"Redis connection failed: {e}")
else:
    print("Redis URL not found, memory will not be persistent.")

# 初始化 Vertex AI
try:
    if GCP_SERVICE_ACCOUNT_JSON_STR:
        credentials_info = json.loads(GCP_SERVICE_ACCOUNT_JSON_STR)
        credentials = service_account.Credentials.from_service_account_info(credentials_info)
        vertexai.init(project=credentials.project_id, location='us-central1', credentials=credentials)
        
        # 依照您的指示設定模型
        text_vision_model = GenerativeModel("gemini-2.5-flash")
        image_gen_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
        print("Vertex AI initialized successfully with user-specified models.")
    else:
        raise ValueError("GCP_SERVICE_ACCOUNT_JSON secret not found.")
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

# --- 功能函式 (維持不變) ---
def translate_prompt_for_drawing(prompt_in_chinese):
    if not text_vision_model: return prompt_in_chinese
    try:
        translation_prompt = f'Translate the following Traditional Chinese text into a vivid, detailed English prompt for an AI image generation model like Imagen 3. Focus on cinematic and artistic keywords. Only output the English prompt: "{prompt_in_chinese}"'
        response = text_vision_model.generate_content(translation_prompt)
        return response.text.strip().replace('"', '')
    except Exception as e:
        print(f"Prompt translation failed: {e}")
        return prompt_in_chinese

def generate_image_with_vertex_ai(prompt):
    if not image_gen_model: return None, "圖片生成功能未啟用。"
    try:
        response = image_gen_model.generate_images(prompt=prompt, number_of_images=1)
        return response.images[0]._image_bytes, "Vertex AI Imagen 繪圖成功！"
    except Exception as e: return None, f"Vertex AI 畫圖時發生錯誤：{e}"

def upload_image_to_cloudinary(image_data):
    try:
        upload_result = cloudinary.uploader.upload(image_data, resource_type="image")
        return upload_result.get('secure_url'), "圖片上傳成功！"
    except Exception as e: return None, f"圖片上傳時發生程式錯誤：{e}"

# --- 核心邏輯 ---
@app.route("/")
def home():
    return "AI Bot (Final Graduation Version with backward compatibility) is Running!"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_message = event.message.text.strip()
    reply_token = event.reply_token
    user_id = event.source.user_id
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    reply_message_obj = []

    if not text_vision_model:
        reply_message_obj.append(TextMessage(text="Gemini AI 功能未啟用或設定錯誤。"))
    elif user_message.lower() in ["清除對話", "忘記對話", "清除記憶"]:
        if redis_client: redis_client.delete(f"chat_history_{user_id}")
        reply_message_obj.append(TextMessage(text="好的，我已經將我們先前的對話紀錄都忘記了。"))
    elif user_message.startswith("畫"):
        prompt_chinese = user_message.split("畫", 1)[1].strip()
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"好的，收到繪圖指令：「{prompt_chinese}」。\n正在翻譯並生成圖片...")]))
        prompt_english = translate_prompt_for_drawing(prompt_chinese)
        image_data, gen_status = generate_image_with_vertex_ai(prompt_english)
        if image_data:
            image_url, upload_status = upload_image_to_cloudinary(image_data)
            if image_url:
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[ImageMessage(original_content_url=image_url, preview_image_url=image_url)]))
            else:
                line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=upload_status)]))
        else:
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=gen_status)]))
        return
    else: # 一般聊天
        history_data = []
        if redis_client:
            history_data_json = redis_client.get(f"chat_history_{user_id}")
            if history_data_json: history_data = json.loads(history_data_json)
        
        # 【核心修正】向下相容的歷史紀錄組裝邏輯
        reconstructed_history = []
        if history_data:
            for message_dict in history_data:
                role = message_dict.get("role")
                parts_list = []
                # 檢查 parts 是不是一個列表
                raw_parts = message_dict.get("parts", [])
                if isinstance(raw_parts, list):
                    for p in raw_parts:
                        # 檢查 p 是字典 (新格式) 還是字串 (舊格式)
                        if isinstance(p, dict):
                            parts_list.append(Part.from_text(p.get("text", "")))
                        elif isinstance(p, str):
                            parts_list.append(Part.from_text(p))
                if role and parts_list:
                    reconstructed_history.append(Content(role=role, parts=parts_list))

        chat_session = text_vision_model.start_chat(history=reconstructed_history)
        response = chat_session.send_message(user_message)
        reply_message_obj.append(TextMessage(text=response.text))
        
        # 儲存時，永遠使用最正確、最標準的新格式
        updated_history = [{"role": c.role, "parts": [{"text": p.text} for p in c.parts]} for c in chat_session.history]
        if redis_client:
            redis_client.set(f"chat_history_{user_id}", json.dumps(updated_history), ex=7200) # 延長對話紀錄至 2 小時
            
    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=reply_message_obj))

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    reply_token = event.reply_token
    message_id = event.message.id
    user_id = event.source.user_id
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    try:
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的圖片了，正在請 Gemini 2.5 flash 進行分析...")]))
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id)
        image_part = Part.from_data(data=message_content, mime_type="image/jpeg")
        prompt = "請用繁體中文，詳細描述這張圖片的內容。"
        if text_vision_model:
            response = text_vision_model.generate_content([image_part, prompt])
            analysis_result = response.text
        else:
            analysis_result = "圖片分析功能未啟用。"
        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"圖片分析結果：\n{analysis_result}")]))
    except Exception as e:
        print(f"Handle Image Message Error: {e}")

# --- 啟動伺服器 ---
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)
