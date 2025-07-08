# === 搭載短期記憶與精確搜尋的最終版 main.py ===

import os
import io
import json
import redis
import re
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
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
GCP_SERVICE_ACCOUNT_JSON_STR = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')
REDIS_URL = os.getenv('REDIS_URL')

redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        print("Redis client connected successfully.")
    except Exception as e:
        print(f"Redis connection failed: {e}")
else:
    print("Redis URL not found, memory will not be persistent.")

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

if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    cloudinary.config(cloud_name=CLOUDINARY_CLOUD_NAME, api_key=CLOUDINARY_API_KEY, api_secret=CLOUDINARY_API_SECRET)

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
        你是一個專業的地點搜尋與資料整理助理。請根據使用者提供的關鍵字，找出最相關的一個地點。
        你的回覆必須是一個 JSON 物件，其中包含三個鍵：
        1. "name": 地點的官方名稱。
        2. "address": 該地點的完整地址。
        3. "phone_number": 該地點的聯絡電話。如果找不到電話，這個鍵的值必須是字串 "無提供電話"。
        請嚴格遵守 JSON 格式，不要回覆任何多餘的文字或解釋。
        使用者查詢的關鍵字是：「{query}」
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
        你是一個專業的在地嚮導與地圖搜尋引擎。請根據使用者提供的經緯度，找出離他最近的 5 個符合「{keyword}」這個查詢條件的地點。
        你的排序必須嚴格以「地理直線距離」作為唯一且最優先的標準，不要考慮店家名氣、評價或任何其他因素。
        建議搜尋半徑約為 2 公里內。
        你的回覆必須是一個 JSON 陣列，陣列中的每個物件都必須包含 "name", "address", 和 "phone_number"。
        如果找不到電話，"phone_number" 的值必須是字串 "無提供電話"。
        請嚴格遵守 JSON 格式，不要回覆任何多餘的文字或解釋。
        使用者位置：緯度 {latitude}, 經度 {longitude}
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

# --- 核心邏輯 ---
@app.route("/")
def home():
    return "AI Bot (Final Version with Short-Term Memory) is Running!"

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
            search_keyword = query.replace("附近", "").strip()
            if not search_keyword: search_keyword = "餐廳"
            if redis_client:
                redis_client.set(f"nearby_query_{user_id}", search_keyword, ex=300)
            line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=f"好的，要搜尋您附近的「{search_keyword}」，請點擊左下角的「+」按鈕，分享您的位置。")]))
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
                parts_list = []
                raw_parts = msg.get("parts", [])
                if isinstance(raw_parts, list):
                    for p in raw_parts:
                        if isinstance(p, dict): parts_list.append(Part.from_text(p.get("text", "")))
                        elif isinstance(p, str): parts_list.append(Part.from_text(p))
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
            messages=[TextMessage(text=f"收到您的位置！正在搜尋您附近的「{search_keyword}」...")]
        )
    )
    places = search_nearby_with_gemini(latitude, longitude, keyword=search_keyword)
    create_location_carousel(places, line_bot_api, user_id)

# --- 啟動伺服器 ---
if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)
