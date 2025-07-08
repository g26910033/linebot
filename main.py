# === 非同步處理 + 指定模型最終版 main.py ===

import os
import io
import json
import redis
import re
import threading
from urllib.parse import quote_plus

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
    TextMessage, ImageMessage, TemplateMessage,
    CarouselTemplate, CarouselColumn, URIAction,
    MessagingApiBlob
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent, LocationMessageContent
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
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
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
        
        # 【核心修正】完全依照您的指示設定模型
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

# --- 功能函式 ---
def clean_text(text):
    cleaned_text = re.sub(r'```json\n|```', '', text)
    cleaned_text = re.sub(r'[*#]', '', cleaned_text)
    return cleaned_text.strip()

def translate_prompt_for_drawing(prompt_in_chinese):
    if not text_vision_model: return prompt_in_chinese
    try:
        translation_prompt = f'Translate the following Traditional Chinese text into a vivid, detailed English prompt for an AI image generation model like Imagen 3. Focus on cinematic and artistic keywords. Only output the English prompt: "{prompt_in_chinese}"'
        response = text_vision_model.generate_content(translation_prompt)
        return clean_text(response.text)
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

def search_location_with_gemini(query):
    if not text_vision_model: return None
    try:
        search_prompt = f"""
        You are a professional location search and data organization assistant. Based on the user's query, find the single most relevant location.
        Your response MUST be a single JSON object containing three keys:
        1. "name": The official name of the location.
        2. "address": The full address of the location.
        3. "phone_number": The contact phone number. If no phone number is found, the value for this key must be the string "無提供電話".
        Strictly adhere to the JSON format. Do not return any extra text or explanations.
        User's query: "{query}"
        """
        response = text_vision_model.generate_content(search_prompt)
        return json.loads(clean_text(response.text))
    except Exception as e:
        print(f"Location search with Gemini failed: {e}")
        return None

def search_nearby_with_gemini(latitude, longitude, keyword="餐廳"):
    if not text_vision_model: return None
    try:
        search_prompt = f"""
        You are a professional local guide and map search engine. Based on the user's provided latitude and longitude, find the 5 closest locations that match the query: "{keyword}".
        You MUST sort the results strictly by geographical distance, not by popularity, ratings, or any other factor.
        The search radius should be approximately 2 kilometers.
        Your response MUST be a JSON array, where each object in the array contains "name", "address", and "phone_number".
        If a phone number is not found for a location, the value for "phone_number" must be the string "無提供電話".
        Strictly adhere to the JSON format. Do not return any extra text or explanations.
        User's location: Latitude {latitude}, Longitude {longitude}
        """
        response = text_vision_model.generate_content(search_prompt)
        return json.loads(clean_text(response.text))
    except Exception as e:
        print(f"Nearby search failed: {e}")
        return None

def create_location_carousel(places_list, line_bot_api, user_id):
    if not places_list:
        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，找不到符合條件的地點。")]))
        return

    columns = []
    for place in places_list[:5]:
        place_name = place.get("name")
        place_address = place.get("address")
        phone_number = place.get("phone_number", "無提供電話")
        
        if not all([place_name, place_address]): continue

        encoded_query = quote_plus(f"{place_name} {place_address}")
        map_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
        
        display_text = f"{place_address}\n電話：{phone_number}"
        
        column = CarouselColumn(
            title=place_name, text=display_text[:60],
            actions=[URIAction(label='在地圖上打開', uri=map_url)]
        )
        columns.append(column)

    if columns:
        template_message = TemplateMessage(alt_text='為您找到推薦地點！', template=CarouselTemplate(columns=columns))
        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[template_message]))
    else:
        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="抱歉，AI回傳的資料格式有誤，無法為您顯示地點。")]))

def run_long_task_in_background(target_func, args_tuple):
    thread = threading.Thread(target=target_func, args=args_tuple)
    thread.start()

def nearby_search_worker(user_id, latitude, longitude, keyword):
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    print(f"背景任務開始：為使用者 {user_id} 搜尋「{keyword}」")
    places = search_nearby_with_gemini(latitude, longitude, keyword=keyword)
    create_location_carousel(places, line_bot_api, user_id)
    print(f"背景任務結束：使用者 {user_id} 的搜尋結果已發送。")
    
# --- 核心邏輯 ---
@app.route("/")
def home():
    return "AI Bot Final Version with Async Tasks is Running!"

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

    if not text_vision_model:
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="Gemini AI 功能未啟用。")]))
        return

    if user_message.lower() in ["清除對話", "忘記對話", "清除記憶"]:
        if redis_client: redis_client.delete(f"chat_history_{user_id}")
        reply_message_obj = [TextMessage(text="好的，我已經將我們先前的對話紀錄都忘記了。")]
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=reply_message_obj))
        return

    elif user_message.startswith("畫"):
        prompt_chinese = user_message.split("畫", 1)[1].strip()
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"好的，收到繪圖指令：「{prompt_chinese}」。\n正在翻譯並生成圖片...")]))
        prompt_english = translate_prompt_for_drawing(prompt_chinese)
        line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"翻譯完成，專業指令為：「{prompt_english}」。\n正在請 Imagen 3 模型繪製...")]))
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

    elif user_message.startswith(("搜尋", "尋找")):
        query = user_message.replace("搜尋", "").replace("尋找", "").strip()
        if "附近" in query:
            parts = query.split("附近")
            search_keyword = (parts[0].strip() or parts[1].strip())
            if not search_keyword: search_keyword = "餐廳"
            if redis_client:
                redis_client.set(f"nearby_query_{user_id}", search_keyword, ex=300)
            line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"好的，要搜尋您附近的「{search_keyword}」，請點擊左下角的「+」按鈕，分享您的位置給我喔！")]))
            return
        
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"收到！正在為您搜尋「{query}」...")]))
        place_data = search_location_with_gemini(query)
        create_location_carousel([place_data] if place_data else [], line_bot_api, user_id)
        return
    
    else: # 一般聊天
        history_data = []
        if redis_client:
            history_data_json = redis_client.get(f"chat_history_{user_id}")
            if history_data_json: history_data = json.loads(history_data_json)
        
        reconstructed_history = []
        if history_data:
            for msg in history_data:
                role = msg.get("role")
                parts_list = [Part.from_text(p.get("text", "")) if isinstance(p, dict) else Part.from_text(p) for p in msg.get("parts", [])]
                if role and parts_list: reconstructed_history.append(Content(role=role, parts=parts_list))

        chat_session = text_vision_model.start_chat(history=reconstructed_history)
        response = chat_session.send_message(user_message)
        cleaned_text = clean_text(response.text)
        reply_message_obj = [TextMessage(text=cleaned_text)]
        
        updated_history = [{"role": c.role, "parts": [{"text": p.text}]} for c in chat_session.history]
        if redis_client:
            redis_client.set(f"chat_history_{user_id}", json.dumps(updated_history), ex=7200)
        
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=reply_message_obj))

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    reply_token = event.reply_token
    message_id = event.message.id
    user_id = event.source.user_id
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    try:
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text="收到您的圖片了，正在請 Gemini 2.5 Flash 進行分析...")]))
        line_bot_blob_api = MessagingApiBlob(api_client)
        message_content = line_bot_blob_api.get_message_content(message_id)
        image_part = Part.from_data(data=message_content, mime_type="image/jpeg")
        prompt = "請用繁體中文，詳細描述這張圖片的內容。"
        if text_vision_model:
            response = text_vision_model.generate_content([image_part, prompt])
            cleaned_analysis_result = clean_text(response.text)
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text=f"圖片分析結果：\n{cleaned_analysis_result}")]))
        else:
            line_bot_api.push_message(PushMessageRequest(to=user_id, messages=[TextMessage(text="圖片分析功能未啟用。")]))
    except Exception as e:
        print(f"Handle Image Message Error: {e}")

@handler.add(MessageEvent, message=LocationMessageContent)
def handle_location_message(event):
    reply_token = event.reply_token
    user_id = event.source.user_id
    latitude = event.message.latitude
    longitude = event.message.longitude
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)

    search_keyword = "餐廳"
    if redis_client:
        stored_keyword = redis_client.get(f"nearby_query_{user_id}")
        if stored_keyword:
            search_keyword = stored_keyword
            redis_client.delete(f"nearby_query_{user_id}")
    
    line_bot_api.reply_message_with_http_info(
        ReplyMessageRequest(
            reply_token=reply_token,
            messages=[TextMessage(text=f"收到您的位置！已將您的「{search_keyword}」搜尋任務交由背景處理，請稍候，完成後會主動通知您。")]
        )
    )
    
    run_long_task_in_background(
        nearby_search_worker, 
        (user_id, latitude, longitude, search_keyword)
    )

# --- 啟動伺服器 ---
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)
