"""
功能說明指令處理器
"""
from linebot.v3.messaging import MessagingApi, TextMessage


class HelpCommandHandler:
    """處理 'help', '功能說明' 等指令的類別。"""

    def __init__(self, line_bot_api: MessagingApi):
        self.line_bot_api = line_bot_api

    def handle(self, reply_token: str) -> None:
        """發送功能說明的訊息。"""
        help_text = """
您好！這是一個功能強大的 AI 助理，您可以這樣使用我：

🤖【AI 對話】
直接輸入任何文字，開始與我對話。

🎨【AI 繪圖】
- `畫 一隻貓`：基本文字生圖。
- 上傳圖片後點選「以圖生圖」，再輸入提示詞（如：`讓牠變成賽博龐克風格`），即可修改圖片。

🖼️【圖片分析】
上傳圖片後，點選「圖片分析」。

📍【地點搜尋】
- `搜尋 台北101`
- `尋找附近的咖啡廳` (需分享位置)

🌦️【天氣查詢】
- `今天台北天氣如何`
- `未來幾天東京的天氣預報`

📰【新聞頭條】
- `新聞` 或 `頭條`

📈【股市查詢】
- `台積電股價` 或 `我想知道TSLA的股價`

✅【互動待辦清單】
- `新增待辦 買牛奶`
- `我的待辦` (會顯示可點擊的清單)

【單位/匯率換算】
- `100公分等於幾公尺`
- `50 USD to TWD`
- `一百台幣多少美元`

📅【新增日曆行程】
- `提醒我明天下午3點開會`
- `新增日曆下週五去看電影`

🌐【網頁/YouTube 影片摘要】
直接貼上網址連結或 YouTube 影片連結。

🗣️【多語言翻譯】
- `翻譯 你好到英文`

🧹【清除對話紀錄】
- `清除對話`
        """
        self.line_bot_api.reply_message(
            reply_token=reply_token,
            messages=[TextMessage(text=help_text.strip())]
        )
