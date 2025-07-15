# 📦 依賴管理說明

## 🎯 統一的 requirements.txt

現在只有一個 `requirements.txt` 檔案，適用於所有部署情況。

### 📋 依賴分類

#### 🔥 核心依賴 (必須)
- `line-bot-sdk==3.12.0` - LINE Bot 核心 SDK (保持此版本最安全)
- `flask==3.0.3` - Web 框架
- `gunicorn==22.0.0` - WSGI 伺服器

#### 🤖 AI 服務 (必須)
- `google-cloud-aiplatform==1.43.0` - Google Vertex AI
- `vertexai>=1.43.0` - Vertex AI SDK
- `google-auth>=2.28.0` - Google 認證
- `google-cloud-storage>=2.14.0` - Google Cloud Storage

#### 🎨 圖片處理 (必須)
- `cloudinary==1.40.0` - 圖片上傳服務
- `Pillow==10.4.0` - 圖片處理

#### 🌐 網路和資料 (必須)
- `requests>=2.32.3` - HTTP 請求
- `beautifulsoup4>=4.12.3` - HTML 解析
- `yt-dlp>=2024.3.10` - YouTube 下載
- `youtube-transcript-api>=0.6.2` - YouTube 字幕

#### ⚡ 可選依賴
- `redis==5.0.3` - 快取和對話記憶 (強烈建議)

#### 🔄 進階功能 (付費方案)
- `celery>=5.3.6` - 背景任務處理 (需要取消註解)

## 🚀 不同部署方案

### 免費方案 (基本功能)
```bash
# 使用預設的 requirements.txt
pip install -r requirements.txt
```
- ✅ 所有 AI 功能
- ✅ 圖片處理和快取 (如果有 Redis)
- ❌ 背景任務處理

### 付費方案 (完整功能)
1. 取消註解 `requirements.txt` 中的 `celery>=5.3.6`
2. 部署 Celery worker
```bash
pip install -r requirements.txt
python celery_worker.py
```
- ✅ 所有功能
- ✅ 背景任務處理
- ✅ 更好的效能

## 🔧 自訂配置

### 不使用 Redis
如果不想使用 Redis，可以註解掉：
```txt
# redis==5.0.3
```
- 仍有所有 AI 功能
- 沒有對話記憶
- 沒有圖片快取

### 最小化部署
如果只需要基本 AI 對話功能，可以移除：
```txt
# yt-dlp>=2024.3.10
# youtube-transcript-api>=0.6.2
# psutil>=5.9.8
```

## 📊 資源使用

| 配置 | RAM 使用 | 啟動時間 | 功能完整度 |
|------|----------|----------|------------|
| 完整版 | ~400MB | 30-45s | 100% |
| 無 Redis | ~350MB | 25-35s | 85% |
| 最小化 | ~300MB | 20-30s | 70% |

## 🛠️ 故障排除

### 常見依賴問題

**Q: 安裝 google-cloud-aiplatform 失敗？**
A: 確保有足夠的記憶體，Render 免費方案可能需要重試

**Q: Pillow 安裝錯誤？**
A: 通常是系統依賴問題，Render 會自動處理

**Q: yt-dlp 更新頻繁？**
A: 可以固定版本，但建議保持更新以支援最新的 YouTube 格式

### 版本衝突解決
如果遇到版本衝突：
1. 檢查錯誤訊息中的衝突套件
2. 調整版本範圍 (例如 `>=` 改為 `==`)
3. 移除非必要的套件

---

💡 **建議**: 對於 Render 免費方案，使用預設配置即可獲得最佳的功能與效能平衡！