
#!/bin/bash
# Render 部署本地測試腳本
# 1. 檢查必要檔案 2. 檢查環境變數 3. 測試依賴安裝 4. 測試啟動 5. 顯示建議
set -e

echo "🚀 準備部署到 Render..."

# 1. 檢查必要檔案
echo "📋 檢查部署檔案..."
required_files=("requirements.txt" "main.py" "render.yaml" "runtime.txt")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 缺少必要檔案: $file" >&2
        exit 1
    fi
done
echo "✅ 所有必要檔案都存在"

# 2. 檢查環境變數
echo "🔧 檢查環境變數..."
required_vars=("LINE_CHANNEL_SECRET" "LINE_CHANNEL_ACCESS_TOKEN" "GCP_SERVICE_ACCOUNT_JSON")
missing_env=0
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "⚠️  環境變數 $var 未設定" >&2
        missing_env=1
    else
        echo "✅ $var 已設定"
    fi
done
if [ $missing_env -eq 1 ]; then
    echo "❌ 請設定所有必要環境變數後再部署。" >&2
    exit 1
fi

# 3. 測試本地構建與依賴安裝
echo "🔨 測試本地構建..."
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt
echo "✅ 依賴安裝成功"

# 4. 測試應用程式啟動（匯入 app）
echo "🧪 測試應用程式..."
python -c "from main import app; print('✅ 應用程式可以正常匯入')"
echo "✅ 應用程式測試通過"

# 5. 顯示建議與結語
echo "🎉 部署準備完成！"
echo "📝 請確保在 Render 控制台設定所有環境變數"
echo "🔗 建議的 Render 設定："
echo "   - Build Command: pip install --no-cache-dir -r requirements.txt"
echo "   - Start Command: gunicorn main:app --bind 0.0.0.0:\$PORT --workers 2 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100"
echo "   - Python Version: 3.11.0"
