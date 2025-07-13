"""
設定 LINE Bot 圖文選單 (Rich Menu) 的腳本。

這個腳本會執行以下操作：
1. 建立一個包含「功能說明」按鈕的圖文選單。
2. 上傳指定的圖片作為選單背景。
3. 將此圖文選單設定為所有使用者的預設選單。

使用方法：
1. 確認您已安裝必要的套件：pip install python-dotenv line-bot-sdk
2. 在專案根目錄建立一個 .env 檔案，並填入您的 LINE_CHANNEL_ACCESS_TOKEN。
   範例 .env 檔案內容：
   LINE_CHANNEL_ACCESS_TOKEN="YOUR_CHANNEL_ACCESS_TOKEN"
3. 準備一張 2500x1686 或 2500x843 像素的圖片，命名為 `rich_menu_background.png`，並放在 `scripts/` 資料夾下。
4. 在專案根目錄執行此腳本：python scripts/setup_rich_menu.py
"""
import os
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    MessageAction
)

def main():
    # 直接使用您提供的 Channel Access Token
    access_token = "Zsr2CyTN6aGMeUF0tnPVhaDfunizTMoRQh3UCDR7PoP4k7LxvrG+t3lyxSEtGxmfo86eIoBRFKGLF9I4/TkFPXCw9glz+0a0XAT3bkZBciNW/Clual2Vg3tXjPaj0AoJ/atYDZZeN8sPpRui5oC3lQdB04t89/1O/w1cDnyilFU="
    if not access_token:
        print("錯誤：Channel Access Token 未設定。")
        return

    configuration = Configuration(access_token=access_token)
    api_client = ApiClient(configuration)
    line_bot_api = MessagingApi(api_client)
    line_bot_blob_api = MessagingApiBlob(api_client)

    # 1. 定義圖文選單的結構
    rich_menu_to_create = RichMenuRequest(
        size={'width': 2500, 'height': 843},
        selected=True,
        name="main_rich_menu",
        chat_bar_text="查看功能",
        areas=[
            RichMenuArea(
                bounds=RichMenuBounds(x=0, y=0, width=2500, height=843),
                action=MessageAction(label='功能說明', text='功能說明')
            )
        ]
    )

    try:
        # 2. 建立圖文選單並取得 ID
        rich_menu_response = line_bot_api.create_rich_menu(rich_menu_request=rich_menu_to_create)
        rich_menu_id = rich_menu_response.rich_menu_id
        print(f"成功建立圖文選單，ID: {rich_menu_id}")

        # 3. 上傳圖文選單的背景圖片
        image_path = os.path.join(os.path.dirname(__file__), 'rich_menu_background.png')
        if not os.path.exists(image_path):
            print(f"錯誤：找不到圖片檔案 {image_path}")
            print("請準備一張圖片並放在正確的位置。")
            # 清除剛剛建立的空選單
            line_bot_api.delete_rich_menu(rich_menu_id)
            print(f"已刪除空的圖文選單 {rich_menu_id}")
            return

        with open(image_path, 'rb') as f:
            # v3 SDK 的正確方法是 set_rich_menu_image
            line_bot_blob_api.set_rich_menu_image(
                rich_menu_id=rich_menu_id,
                body=bytearray(f.read()),
                _headers={'Content-Type': 'image/png'}
            )
        print("成功上傳圖文選單圖片。")

        # 4. 將此圖文選單設為預設
        line_bot_api.set_default_rich_menu(rich_menu_id)
        print("成功將此圖文選單設為預設。")

    except Exception as e:
        print(f"發生錯誤：{e}")

if __name__ == "__main__":
    main()
