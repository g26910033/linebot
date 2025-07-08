# === Render 平台最終穩定版 main.py ===

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
# 【不再需要 replit.db】
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

# 【核心修正】使用 Python 字典作為暫時記憶體
chat_histories = {} # 用於儲存 ChatSession 的對話紀錄
long_term_memory = {} # 用於儲存「記住/查詢」的內容

# 使用服務帳戶金鑰初始化 Vertex AI
try:
    # Render 會自動偵測 GOOGLE_APPLICATION_CREDENTIALS
    vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
    text_vision_model = GenerativeModel("gemini-2.5-pro")
    image_gen_model = ImageGenerationModel.from_pretrained("imagen-3.0-generate-002")
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

# --- 功能函式 (維持不變) ---
def translate_prompt(prompt_in_chinese, task_type="image"):
    if not text_vision_model: return prompt_in_chinese
    try:
        task_description = "video generation" if task_type == "video" else "image generation"
        translation_prompt = f'Translate the following Traditional Chinese text into a vivid, detailed English prompt for an AI {task_description} model: "{prompt_in_chinese}"'
        response = text_vision_model.generate_content(translation_prompt)
        return response.text.strip()
    except Exception: return prompt_in_chinese

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
    return "AI Bot is running perfectly on Render!"

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
        if user_id in chat_histories:
            del chat_histories[user_id]
        reply_message_obj.append(TextMessage(text="好的，我已經將我們先前的對話紀錄都忘記了。"))
    elif user_message.startswith("記住"):
        parts = user_message.split("是", 1)
        if len(parts) == 2:
            key = parts[0][2:].strip()
            value = parts[1].strip()
            long_term_memory[key] = value
            reply_message_obj.append(TextMessage(text=f"好的，我記住了「{key}」。"))
        else:
            reply_message_obj.append(TextMessage(text="指令格式錯誤。請用「記住 [關鍵字] 是 [內容]」"))
    elif user_message.startswith("查詢"):
        key = user_message[2:].strip()
        value = long_term_memory.get(key)
        if value:
            reply_message_obj.append(TextMessage(text=f"我記得「{key}」是「{value}」。"))
        else:
            reply_message_obj.append(TextMessage(text=f"抱歉，在我的長期記憶中找不到「{key}」的紀錄。"))
    elif user_message.startswith("畫"):
        prompt_chinese = user_message.split("畫", 1)[1].strip()
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"好的，收到繪圖指令：「{prompt_chinese}」。\n正在翻譯並生成圖片...")]))
        prompt_english = translate_prompt(prompt_chinese, "image")
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
        history_data = chat_histories.get(user_id, [])
        chat_session = text_vision_model.start_chat(history=history_data)
        response = chat_session.send_message(user_message)
        reply_message_obj.append(TextMessage(text=response.text))
        chat_histories[user_id] = chat_session.history

    line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=reply_message_obj))

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    # (圖片識別邏輯維持不變，此處省略以保持簡潔)
    reply_token = event.reply_token
    message_id = event.message.id
    user_id = event.source.user_id
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    try:
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的圖片了，正在請 Gemini 1.5 Pro 進行分析...")]))
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
    serve(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))