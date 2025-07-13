# 🚀 Render 部署優化指南

## 📋 部署前檢查清單

### 1. 必要檔案確認
- [x] `requirements.txt` - 固定版本依賴
- [x] `runtime.txt` - Python 版本指定
- [x] `render.yaml` - 服務配置
- [x] `Procfile` - 啟動命令
- [x] `.renderignore` - 排除不必要檔案

### 2. 環境變數設定
在 Render 控制台設定以下環境變數：

```bash
# LINE Bot 設定
LINE_CHANNEL_SECRET=your_channel_secret
LINE_CHANNEL_ACCESS_TOKEN=your_access_token

# Google Cloud 設定
GCP_SERVICE_ACCOUNT_JSON={"type":"service_account",...}

# Cloudinary 設定
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Redis 設定 (可選)
REDIS_URL=redis://...

# 平台識別
RENDER=true
```

## ⚡ 部署速度優化

### 1. 構建時間優化
```yaml
# render.yaml 中的優化設定
buildCommand: |
  pip install --upgrade pip
  pip install --no-cache-dir -r requirements.txt
```

**關鍵優化點：**
- 使用 `--no-cache-dir` 減少磁碟使用
- 固定依賴版本避免解析時間
- 移除開發依賴

### 2. 依賴管理最佳實踐
```txt
# requirements.txt 優化
line-bot-sdk==3.12.0        # 固定版本
flask==3.0.0                # 避免 >= 語法
google-cloud-aiplatform==1.42.1
```

### 3. 映像檔大小優化
- 使用 `.renderignore` 排除不必要檔案
- 移除測試和開發工具
- 壓縮靜態資源

## 🔧 配置最佳實踐

### 1. 建議的啟動命令
```bash
# 基本配置
gunicorn main:app --bind 0.0.0.0:$PORT --workers 2

# 優化配置
gunicorn main:app \
  --bind 0.0.0.0:$PORT \
  --workers 2 \
  --timeout 120 \
  --keep-alive 2 \
  --max-requests 1000 \
  --max-requests-jitter 100
```

### 2. Worker 數量計算
```python
# 根據 Render 方案選擇
Starter Plan:  1-2 workers (0.5 CPU)
Standard Plan: 2-3 workers (1 CPU)  
Pro Plan:      3-4 workers (2+ CPU)
```

### 3. 快取策略
```python
# 記憶體快取 (Redis 不可用時)
CACHE_TIMEOUT = 300  # 5 分鐘
MAX_CACHE_SIZE = 1000  # 最大快取項目

# Redis 快取 (推薦)
REDIS_TTL = 3600  # 1 小時
```

## 📊 資源使用優化

### 1. 實例類型選擇建議

| 方案 | CPU | RAM | 適用場景 |
|------|-----|-----|----------|
| Starter | 0.5 | 512MB | 開發/測試 |
| Standard | 1 | 2GB | 小型生產 |
| Pro | 2+ | 4GB+ | 大型生產 |

### 2. 自動擴展設定
```yaml
# render.yaml
services:
  - type: web
    autoDeploy: true
    plan: standard
    scaling:
      minInstances: 1
      maxInstances: 3
```

### 3. 靜態資源處理
```python
# Flask 配置優化
app.config.update({
    'SEND_FILE_MAX_AGE_DEFAULT': 31536000,  # 1 年快取
    'JSON_SORT_KEYS': False,
    'JSONIFY_PRETTYPRINT_REGULAR': False
})
```

## 🔍 監控和除錯

### 1. 健康檢查端點
```python
@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "uptime": get_uptime(),
        "services": check_services()
    }
```

### 2. 日誌監控
```python
# 結構化日誌
logger.info("Request processed", extra={
    "user_id": user_id,
    "processing_time": elapsed_time,
    "status": "success"
})
```

### 3. 效能監控
- 使用 Render 內建監控
- 設定告警閾值
- 監控回應時間和錯誤率

## 🚨 常見問題解決

### 1. 部署失敗
```bash
# 檢查日誌
render logs --service your-service-name

# 常見原因
- 環境變數未設定
- 依賴版本衝突
- 記憶體不足
```

### 2. 效能問題
```python
# 記憶體使用優化
- 限制對話歷史長度
- 使用生成器處理大數據
- 及時釋放資源
```

### 3. 連線問題
```python
# 連線池配置
redis_client = redis.ConnectionPool(
    max_connections=10,
    retry_on_timeout=True
)
```

## 📈 效能基準

### 目標指標
- 冷啟動時間: < 30 秒
- 回應時間: < 2 秒
- 記憶體使用: < 80%
- CPU 使用: < 70%

### 監控命令
```bash
# 本地測試
python scripts/deploy.sh

# 效能測試
ab -n 100 -c 10 https://your-app.onrender.com/health
```

這個優化方案將大幅提升您的 LINE Bot 在 Render 平台上的部署效率和執行效能。