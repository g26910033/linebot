import os
import sys
import subprocess
from app import LineBotApp
from utils.logger import get_logger

# 這個腳本的目的是在啟動 Gunicorn 之前，先執行一些前置任務，
# 例如設定圖文選單，以確保這些任務在一個乾淨的、單一的程序中完成。

logger = get_logger(__name__)

def main():
    # 1. 執行圖文選單設定
    logger.info("Executing pre-start tasks: Setting up Rich Menu...")
    try:
        # 我們需要一個 app 的實例來取得 configuration
        bot_app_for_setup = LineBotApp()
        bot_app_for_setup._setup_default_rich_menu()
        logger.info("Rich Menu setup task completed.")
    except Exception as e:
        logger.error(f"An error occurred during pre-start Rich Menu setup: {e}", exc_info=True)
        # 即使設定失敗，我們仍然嘗試啟動伺服器
        logger.warning("Continuing server startup despite Rich Menu setup failure.")

    # 2. 準備 Gunicorn 指令
    port = os.environ.get("PORT", "8080")
    gunicorn_command = [
        "gunicorn",
        "app:create_app()",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "2",
        "--timeout", "60",
        "--keep-alive", "5",
        "--max-requests", "2000",
        "--max-requests-jitter", "200"
    ]

    logger.info(f"Starting Gunicorn server with command: {' '.join(gunicorn_command)}")

    # 3. 執行 Gunicorn
    try:
        subprocess.run(gunicorn_command, check=True)
    except subprocess.CalledProcessError as e:
        logger.critical(f"Gunicorn failed to start: {e}", exc_info=True)
        sys.exit(1)
    except FileNotFoundError:
        logger.critical("Gunicorn command not found. Is Gunicorn installed?", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
