# 🔧 Render 部署問題排除指南

## 常見錯誤及解決方案

### 1. Pillow 安裝錯誤

**錯誤訊息：**
```
KeyError: '__version__'
Getting requirements to build wheel did not run successfully
```

**解決方案：**
```bash
# 方案 1: 更新 Pillow 版本
pip install Pillow==10.4.0

# 方案 2: 使用較舊但穩定的版本
pip install Pillow==9.5.0

# 方案 3: 安裝構建工具
pip install --upgrade pip wheel setuptools
```

### 2. Python 版本相容性

**問題：** Python 3.13 與某些套件不相容

**解決方案：**
```txt
# runtime.txt
python-3.11
```

### 3. 記憶體不足錯誤

**錯誤訊息：**
```
MemoryError during build
```

**解決方案：**
```yaml
# render.yaml
services:
  - type: web
    plan: standard  # 升級到更大記憶體
```

### 4. 構建超時

**解決方案：**
```bash
# 使用最小化依賴
pip install -r requirements-minimal.txt

# 分階段安裝
pip install line-bot-sdk flask
pip install google-cloud-aiplatform
pip install cloudinary redis gunicorn
```

### 5. 環境變數問題

**檢查清單：**
- [ ] LINE_CHANNEL_SECRET
- [ ] LINE_CHANNEL_ACCESS_TOKEN  
- [ ] GCP_SERVICE_ACCOUNT_JSON
- [ ] CLOUDINARY_CLOUD_NAME
- [ ] CLOUDINARY_API_KEY
- [ ] CLOUDINARY_API_SECRET

### 6. 啟動失敗

**常見原因：**
```python
# 檢查 main.py 是否正確匯出 app
from app import create_app
app = create_app()

# 確保 gunicorn 命令正確
gunicorn main:app --bind 0.0.0.0:$PORT
```

## 🚀 快速修復腳本

```bash
# 執行依賴修復
python scripts/fix-dependencies.py

# 測試本地啟動
python main.py

# 檢查依賴衝突
pip check
```

## 📞 獲取幫助

如果問題持續存在：
1. 檢查 Render 日誌
2. 使用最小化依賴測試
3. 嘗試降級 Python 版本
4. 聯繫技術支援