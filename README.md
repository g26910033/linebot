# AI LINE Bot

一個功能豐富的 AI LINE Bot，整合了 Google Vertex AI 的文字對話、圖片分析和圖片生成功能。

## 功能特色

### 🤖 AI 對話
- 使用 Gemini 2.5 Flash 模型進行智能對話
- 支援對話歷史記錄和上下文理解
- 可清除對話記錄重新開始

### 🎨 圖片生成
- 使用 Imagen 3.0 模型生成高品質圖片
- 自動將中文提示詞翻譯為英文專業提示詞
- 支援各種藝術風格和主題

### 🔍 圖片分析
- 上傳圖片即可獲得詳細的內容分析
- 支援多種圖片格式
- 提供繁體中文分析結果

### 📍 地點搜尋
- 智能地點搜尋功能
- 附近地點推薦（需分享位置）
- 整合 Google Maps 連結

## 使用方式

### 基本對話
直接發送文字訊息即可與 AI 對話。

### 圖片生成
```
畫 一隻可愛的貓咪在花園裡玩耍
```

### 圖片分析
直接上傳圖片，Bot 會自動分析內容。

### 地點搜尋
```
搜尋 台北101
尋找 附近的餐廳
```

### 清除對話
```
清除對話
忘記對話
清除記憶
```

## 技術架構

### 核心技術
- **Flask**: Web 框架
- **LINE Bot SDK**: LINE 訊息處理
- **Google Vertex AI**: AI 模型服務
- **Redis**: 對話記錄快取
- **Cloudinary**: 圖片儲存服務

### 程式架構
```
├── config/
│   └── settings.py          # 應用程式設定
├── services/
│   ├── ai_service.py        # AI 服務
│   └── storage_service.py   # 儲存服務
├── handlers/
│   └── message_handlers.py  # 訊息處理器
├── utils/
│   └── logger.py           # 日誌工具
├── app.py                  # 主應用程式
├── main.py                 # 程式入口點
└── requirements.txt        # 依賴套件
```

## 環境設定

### 必要環境變數
```bash
# LINE Bot 設定
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_access_token

# Google Cloud 設定
GCP_SERVICE_ACCOUNT_JSON=your_service_account_json

# Cloudinary 設定
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Redis 設定 (可選)
REDIS_URL=your_redis_url

# 應用程式設定
PORT=10000
DEBUG=False
```

## 部署說明

### 本地開發
```bash
# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
export LINE_CHANNEL_SECRET=your_secret
export LINE_CHANNEL_ACCESS_TOKEN=your_token
# ... 其他環境變數

# 啟動應用程式
python main.py
```

### 生產環境
```bash
# 使用 Gunicorn
gunicorn app:app --bind 0.0.0.0:10000

# 或使用 Waitress
python main.py
```

## API 端點

- `GET /` - 應用程式狀態
- `GET /health` - 健康檢查
- `POST /callback` - LINE Webhook

## 設計原則

### 1. 模組化設計
- 清楚分離不同功能模組
- 降低程式碼耦合度
- 提升可維護性

### 2. 錯誤處理
- 完整的異常處理機制
- 詳細的日誌記錄
- 優雅的錯誤回應

### 3. 效能優化
- 背景任務處理耗時操作
- Redis 快取減少重複計算
- 適當的資源管理

### 4. 安全性
- 環境變數管理敏感資訊
- 輸入驗證和清理
- 適當的權限控制

## 開發指南

### 新增功能
1. 在 `services/` 中實作業務邏輯
2. 在 `handlers/` 中新增訊息處理器
3. 在 `app.py` 中註冊新的處理器

### 測試
```bash
# 執行測試
pytest

# 測試覆蓋率
pytest --cov=.
```

### 程式碼品質
```bash
# 格式化程式碼
black .

# 檢查程式碼風格
flake8 .
```

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request 來改善這個專案。