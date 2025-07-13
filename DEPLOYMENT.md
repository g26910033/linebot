
# 🚀 Render 部署優化指南

> 本指南涵蓋部署前檢查、效能/安全/依賴/監控最佳實踐，協助你在 Render 平台高效穩定運行 LINE Bot。

---

## 📋 部署前檢查清單

### 1. 必要檔案確認

| 檔案              | 說明               |
|-------------------|--------------------|
| requirements.txt  | 固定版本依賴       |
| runtime.txt       | Python 版本指定    |
| render.yaml       | 服務配置           |
| Procfile          | 啟動命令           |
| .renderignore     | 排除不必要檔案     |

### 2. 環境變數設定
請於 Render 控制台設定下列環境變數（建議複製貼上，勿留空）：

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


## ⚡ 部署速度與映像檔優化

### 1. 構建時間優化
```yaml
# render.yaml
buildCommand: |
  pip install --upgrade pip
  pip install --no-cache-dir -r requirements.txt
```
**重點：**
- `--no-cache-dir` 減少磁碟用量
- 固定依賴版本，避免解析等待
- requirements.txt 僅保留生產依賴

### 2. 依賴管理最佳實踐
```txt
# requirements.txt 範例
line-bot-sdk==3.12.0
flask==3.0.0
google-cloud-aiplatform==1.42.1
# ... 其餘依賴 ...
```

### 3. 映像檔大小優化
- `.renderignore` 排除測試/開發/暫存檔
- 不要將 .git、venv、測試資料夾等打包進映像檔
- 壓縮靜態資源（如圖片、JS、CSS）


## 🔧 配置與效能最佳實踐

### 1. 建議啟動命令（Gunicorn）
```bash
# 優化後
gunicorn "app:create_app()" \
  --bind 0.0.0.0:$PORT \
  --workers 3 \
  --timeout 60 \
  --keep-alive 5 \
  --max-requests 2000 \
  --max-requests-jitter 200
```

### 2. Worker 數量建議
| 方案         | 建議 workers | CPU 配置 |
|--------------|--------------|----------|
| Starter      | 1-2          | 0.5      |
| Standard     | 2-3          | 1        |
| Pro          | 3-4          | 2+       |

### 3. 快取策略
```python
# 記憶體快取（無 Redis 時）
CACHE_TIMEOUT = 300  # 5 分鐘
MAX_CACHE_SIZE = 1000
# Redis 快取（推薦）
REDIS_TTL = 3600  # 1 小時
```


## 📊 資源與自動擴展優化

### 1. 實例類型選擇
| 方案     | CPU  | RAM   | 適用場景   |
|----------|------|-------|------------|
| Starter  | 0.5  | 512MB | 開發/測試  |
| Standard | 1    | 2GB   | 小型生產   |
| Pro      | 2+   | 4GB+  | 大型生產   |

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


## 🔍 監控、日誌與除錯

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

### 2. 結構化日誌監控
```python
logger.info("Request processed", extra={
    "user_id": user_id,
    "processing_time": elapsed_time,
    "status": "success"
})
```

### 3. 效能監控
- 使用 Render 內建監控
- 設定告警閾值
- 監控回應時間、錯誤率、資源用量


## 🚨 常見問題與解決方案

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
- 限制對話歷史長度
- 使用生成器處理大數據
- 及時釋放資源

### 3. 連線問題
```python
# Redis 連線池配置
redis_client = redis.ConnectionPool(
    max_connections=10,
    retry_on_timeout=True
)
```


## 📈 效能基準與監控

### 目標指標
- 冷啟動時間：< 30 秒
- 回應時間：< 2 秒
- 記憶體使用：< 80%
- CPU 使用：< 70%

### 監控命令
```bash
# 本地測試
python scripts/deploy.sh
# 效能測試
ab -n 100 -c 10 https://your-app.onrender.com/health
```

---

> 依本指南優化，將大幅提升您的 LINE Bot 在 Render 平台的部署效率、穩定性與可維護性。
