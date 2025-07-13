# main.py

# 在所有其他 import 之前，最優先載入 .env 檔案
from dotenv import load_dotenv
load_dotenv()

# 現在可以安全地 import 其他模組
from app import create_app
from utils.logger import get_logger

logger = get_logger(__name__)

# 建立 Flask app 實例
# create_app 會自動讀取已載入的環境變數
app = create_app()

if __name__ == "__main__":
    try:
        # 從 app 的 config 中取得設定
        port = app.config.get("PORT", 8080)
        debug_mode = app.config.get("DEBUG", True)

        logger.info(f"Starting Flask development server on http://0.0.0.0:{port} (debug mode: {debug_mode}).")
        # 在本地端開發時，使用 Flask 內建的伺服器即可
        app.run(host="0.0.0.0", port=port, debug=debug_mode)

    except Exception as e:
        logger.critical("Application startup failed critically.", exc_info=e)
        raise