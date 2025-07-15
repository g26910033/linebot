# ✅ Render 免費方案部署檢查清單

## 🚀 部署前準備

### 1. **GCP 設定檢查**
- [ ] **GCP 專案已建立**
- [ ] **服務帳戶已建立** (具備以下權限)
  - [ ] `roles/aiplatform.user` - Vertex AI 使用權限
  - [ ] `roles/storage.objectAdmin` - Cloud Storage 權限
  - [ ] `roles/ml.developer` - ML 開發權限
- [ ] **API 已啟用**
  - [ ] Vertex AI API
  - [ ] Cloud Storage API
  - [ ] AI Platform API
  - [ ] Cloud Resource Manager API
- [ ] **服務帳戶金鑰已下載** (JSON 格式)

### 2. **第三方服務設定**
- [ ] **LINE Developers Console**
  - [ ] Bot 已建立
  - [ ] Channel Secret 已取得
  - [ ] Channel Access Token 已取得
- [ ] **Cloudinary 帳戶**
  - [ ] 帳戶已建立
  - [ ] Cloud Name, API Key, API Secret 已取得
- [ ] **OpenWeather API**
  - [ ] API Key 已取得
- [ ] **NewsAPI**
  - [ ] API Key 已取得
- [ ] **Redis 服務** (強烈建議)
  - [ ] Render Redis 或外部 Redis URL

## 🔧 Render 部署設定

### 1. **建立 Web Service**
- [ ] 連接 GitHub 儲存庫
- [ ] 選擇 `linebot` 資料夾作為根目錄
- [ ] Runtime: `Python 3`

### 2. **Build & Deploy 設定**
```bash
# Build Command (複製貼上)
pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

# Start Command (複製貼上)
gunicorn "app:create_app()" --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 60 --keep-alive 2 --max-requests 1000 --preload
```

### 3. **環境變數設定**

#### 必要變數 ✅
```bash
# 效能優化
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# LINE Bot (必要)
LINE_CHANNEL_SECRET=你的LINE頻道密鑰
LINE_CHANNEL_ACCESS_TOKEN=你的LINE存取權杖

# Google Cloud (必要)
GCP_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}

# Cloudinary (必要)
CLOUDINARY_CLOUD_NAME=你的雲端名稱
CLOUDINARY_API_KEY=你的API金鑰
CLOUDINARY_API_SECRET=你的API密鑰

# 外部 API (必要)
OPENWEATHER_API_KEY=你的OpenWeather金鑰
NEWS_API_KEY=你的NewsAPI金鑰
```

#### 可選變數 ⚡
```bash
# Redis (強烈建議)
REDIS_URL=redis://...

# 股票功能 (可選)
FINNHUB_API_KEY=你的Finnhub金鑰

# 除錯模式 (生產環境建議 false)
DEBUG=false
```

## 🧪 部署後測試

### 1. **基本功能測試**
- [ ] **服務健康檢查**
  ```bash
  curl https://your-app.onrender.com/
  # 應返回: {"status": "running"}
  ```

### 2. **LINE Bot 設定**
- [ ] **設定 Webhook URL**
  - 進入 LINE Developers Console
  - Webhook URL: `https://your-app.onrender.com/callback`
  - 啟用 "Use webhook"
- [ ] **測試 Webhook**
  - 點擊 "Verify" 按鈕
  - 應顯示成功訊息

### 3. **功能測試清單**
- [ ] **基本對話** - 傳送 "你好"
- [ ] **天氣查詢** - 傳送 "台北天氣"
- [ ] **新聞查詢** - 傳送 "新聞"
- [ ] **圖片上傳** - 上傳任意圖片
- [ ] **圖片分析** - 上傳圖片後選擇分析
- [ ] **圖片生成** - 傳送 "畫一隻貓"
- [ ] **翻譯功能** - 傳送 "Hello 翻譯中文"
- [ ] **YouTube 摘要** - 傳送 YouTube 連結

## 🔍 故障排除

### 常見問題檢查

#### 部署失敗
- [ ] 檢查 Build 日誌中的錯誤訊息
- [ ] 確認 `requirements.txt` 格式正確
- [ ] 檢查 Python 版本相容性

#### LINE Bot 無回應
- [ ] 確認 Webhook URL 設定正確
- [ ] 檢查環境變數 `LINE_CHANNEL_SECRET` 和 `LINE_CHANNEL_ACCESS_TOKEN`
- [ ] 查看 Render 服務日誌

#### Google 服務錯誤
- [ ] 確認 `GCP_SERVICE_ACCOUNT_JSON` 格式正確 (完整 JSON)
- [ ] 檢查 GCP 專案 ID 是否正確
- [ ] 確認 API 已啟用且有足夠權限
- [ ] 檢查配額使用情況

#### 圖片功能問題
- [ ] 確認 Cloudinary 環境變數設定
- [ ] 檢查 Cloudinary 帳戶配額
- [ ] 測試 Cloudinary 連線

## 📊 效能監控

### 1. **Render Dashboard 監控**
- [ ] CPU 使用率 (應 < 80%)
- [ ] 記憶體使用率 (應 < 400MB)
- [ ] 回應時間 (應 < 5 秒)
- [ ] 錯誤率 (應 < 5%)

### 2. **GCP Console 監控**
- [ ] Vertex AI API 使用量
- [ ] 配額使用情況
- [ ] 錯誤日誌檢查

### 3. **功能監控**
- [ ] 快取命中率 (Redis 連線時)
- [ ] API 回應時間
- [ ] 使用者互動統計

## 🎯 優化建議

### 短期優化
- [ ] 設定 Redis 快取 (如尚未設定)
- [ ] 監控 API 使用量避免超限
- [ ] 定期檢查服務日誌

### 長期優化
- [ ] 考慮升級到付費方案 (避免冷啟動)
- [ ] 實施使用者行為分析
- [ ] 加入更多 AI 功能

## 🆘 緊急聯絡

### 服務中斷處理
1. **檢查 Render 狀態頁面**
2. **查看服務日誌**
3. **重新部署服務**
4. **檢查第三方服務狀態**

### 配額超限處理
1. **檢查 GCP Console 配額**
2. **等待配額重置 (通常每分鐘)**
3. **考慮升級 GCP 方案**
4. **優化 API 使用頻率**

---

🎉 **完成所有檢查項目後，您的 LINE Bot 就可以穩定運行了！**

預期部署時間: **3-5 分鐘**
預期冷啟動時間: **30-60 秒**