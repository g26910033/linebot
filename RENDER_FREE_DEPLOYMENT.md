# 🆓 Render 免費方案部署指南

## 📋 手動部署步驟

由於 Render 免費方案沒有 Blueprint (render.yaml) 功能，需要手動設定服務。

### 1. **創建 Web Service**

1. 登入 Render Dashboard
2. 點擊 "New +" → "Web Service"
3. 連接您的 GitHub 儲存庫
4. 選擇 `linebot` 資料夾作為根目錄

### 2. **基本設定**

| 設定項目 | 值 |
|---------|---|
| **Name** | `ai-linebot` (或您喜歡的名稱) |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install --upgrade pip && pip install -r requirements.txt` |
| **Start Command** | `gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 2 --timeout 60` |

> 💡 **注意**: 現在只有一個 `requirements.txt` 檔案，已經為免費方案優化！

### 3. **環境變數設定**

在 Render Dashboard 的 Environment 頁面加入以下變數：

#### 必要環境變數
```
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
LINE_CHANNEL_SECRET=你的LINE頻道密鑰
LINE_CHANNEL_ACCESS_TOKEN=你的LINE存取權杖
GCP_SERVICE_ACCOUNT_JSON=你的GCP服務帳戶JSON(完整內容)
CLOUDINARY_CLOUD_NAME=你的Cloudinary雲端名稱
CLOUDINARY_API_KEY=你的Cloudinary API金鑰
CLOUDINARY_API_SECRET=你的Cloudinary API密鑰
OPENWEATHER_API_KEY=你的OpenWeather API金鑰
NEWS_API_KEY=你的NewsAPI金鑰
```

#### 可選環境變數
```
FINNHUB_API_KEY=你的Finnhub API金鑰(股票功能)
REDIS_URL=你的Redis連線URL(如果有外部Redis)
DEBUG=false
PORT=10000
```

### 4. **Redis 設定 (可選)**

#### 選項 A: 使用 Render Redis (推薦)
1. 創建新的 Redis 服務: "New +" → "Redis"
2. 複製 Internal Redis URL
3. 在 Web Service 環境變數中設定 `REDIS_URL`

#### 選項 B: 使用外部 Redis
- 可使用 Redis Cloud、Upstash 等免費服務
- 將連線 URL 設定到 `REDIS_URL` 環境變數

#### 選項 C: 不使用 Redis
- 不設定 `REDIS_URL` 環境變數
- 功能仍正常，但沒有快取和對話記憶

### 5. **部署設定**

| 設定項目 | 建議值 |
|---------|-------|
| **Auto-Deploy** | ✅ 啟用 |
| **Branch** | `main` 或 `master` |
| **Root Directory** | `linebot` |

## 🚀 部署後驗證

### 1. **檢查服務狀態**
訪問您的 Render URL: `https://your-service-name.onrender.com`
應該看到: `{"status": "running"}`

### 2. **設定 LINE Webhook**
1. 進入 LINE Developers Console
2. 設定 Webhook URL: `https://your-service-name.onrender.com/callback`
3. 啟用 "Use webhook"

### 3. **測試功能**
- 傳送訊息給您的 LINE Bot
- 測試圖片上傳和分析
- 測試天氣查詢等功能

## ⚡ 免費方案限制與優化

### 限制
- **睡眠模式**: 15分鐘無活動後會休眠
- **冷啟動**: 休眠後首次請求需要 30-60 秒
- **資源限制**: 512MB RAM, 0.1 CPU
- **無背景任務**: 不支援 Celery worker

### 優化策略
1. **快取機制**: 已實作的圖片快取仍然有效
2. **輕量化**: 移除不必要的依賴
3. **保持活躍**: 可設定定時 ping 服務 (但要注意流量限制)

## 🔧 故障排除

### 常見問題

**Q: 部署失敗，顯示依賴錯誤？**
A: 檢查 `requirements.txt` 格式，確保所有套件版本相容

**Q: LINE Bot 沒有回應？**
A: 
1. 檢查 Webhook URL 設定
2. 查看 Render 日誌是否有錯誤
3. 確認環境變數設定正確

**Q: 圖片功能無法使用？**
A: 檢查 GCP 和 Cloudinary 環境變數設定

**Q: 服務經常休眠？**
A: 這是免費方案的限制，考慮升級到付費方案或使用 ping 服務

### 查看日誌
在 Render Dashboard → 您的服務 → Logs 頁面查看詳細日誌

## 📊 監控建議

### 免費方案監控
- 定期檢查 Render Dashboard 的服務狀態
- 監控日誌中的錯誤訊息
- 使用 LINE Bot 的健康檢查功能

### 簡單的健康檢查
```bash
# 檢查服務是否正常
curl https://your-service-name.onrender.com/

# 應該返回: {"status": "running"}
```

## 🎯 升級建議

當您準備升級到付費方案時：
1. 可啟用 Celery 背景任務處理
2. 使用 Blueprint (render.yaml) 自動部署
3. 增加資源配置以提升效能
4. 啟用自動擴展功能

---

💡 **提示**: 即使在免費方案下，您的 LINE Bot 仍然擁有完整的 AI 功能和圖片快取優化！