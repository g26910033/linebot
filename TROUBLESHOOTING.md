
# 🔧 Render 部署問題排除指南

> 本指南彙整 Render 部署常見錯誤、快速修復腳本與技術支援建議，協助你高效解決問題。

---

## 🚨 常見錯誤與解決方案

### 1. Pillow 安裝錯誤
**錯誤訊息：**
```
KeyError: '__version__'
Getting requirements to build wheel did not run successfully
```
**解決方式：**
- Pillow 10.4.0 以上通常可解決
- 若失敗，嘗試 9.5.0 或升級 pip/wheel/setuptools
```bash
pip install Pillow==10.4.0
pip install Pillow==9.5.0
pip install --upgrade pip wheel setuptools
```

### 2. Python 版本相容性
**問題：** Python 3.13 與部分套件不相容
**解決方式：**
```txt
# runtime.txt
python-3.11
```

### 3. 記憶體不足錯誤
**錯誤訊息：**
```
MemoryError during build
```
**解決方式：**
- 升級方案（standard 以上）
```yaml
services:
  - type: web
    plan: standard
```

### 4. 構建超時
**解決方式：**
- 使用最小化依賴
- 分階段安裝
```bash
pip install -r requirements-minimal.txt
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
**常見原因與檢查：**
```python
# main.py 是否正確匯出 app
from app import create_app
app = create_app()
# gunicorn 命令格式
gunicorn main:app --bind 0.0.0.0:$PORT
```

---

## �️ 快速修復腳本

```bash
# 依賴修復
python scripts/fix-dependencies.py
# 本地啟動測試
python main.py
# 依賴衝突檢查
pip check
```

---

## 📞 技術支援與進階排查

1. 檢查 Render 日誌（render logs --service ...）
2. 測試 requirements-minimal.txt
3. 降級 Python 版本（如 3.11）
4. 搜尋官方論壇/社群
5. 聯繫 Render 技術支援