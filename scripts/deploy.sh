#!/bin/bash

# Render 部署腳本
# 用於本地測試部署配置

echo "🚀 準備部署到 Render..."

# 檢查必要檔案
echo "📋 檢查部署檔案..."
required_files=("requirements.txt" "main.py" "render.yaml" "runtime.txt")

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ 缺少必要檔案: $file"
        exit 1
    fi
done

echo "✅ 所有必要檔案都存在"

# 檢查環境變數
echo "🔧 檢查環境變數..."
required_vars=("LINE_CHANNEL_SECRET" "LINE_CHANNEL_ACCESS_TOKEN" "GCP_SERVICE_ACCOUNT_JSON")

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "⚠️  環境變數 $var 未設定"
    else
        echo "✅ $var 已設定"
    fi
done

# 測試本地構建
echo "🔨 測試本地構建..."
python -m pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ 依賴安裝成功"
else
    echo "❌ 依賴安裝失敗"
    exit 1
fi

# 測試應用程式啟動
echo "🧪 測試應用程式..."
python -c "from main import app; print('✅ 應用程式可以正常匯入')"

if [ $? -eq 0 ]; then
    echo "✅ 應用程式測試通過"
else
    echo "❌ 應用程式測試失敗"
    exit 1
fi

echo "🎉 部署準備完成！"
echo "📝 請確保在 Render 控制台設定所有環境變數"
echo "🔗 建議的 Render 設定："
echo "   - Build Command: pip install -r requirements.txt"
echo "   - Start Command: gunicorn main:app --bind 0.0.0.0:\$PORT --workers 2"
echo "   - Python Version: 3.11.0"