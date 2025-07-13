"""
主程式入口點，保持向後相容性
"""
from app import create_app
from utils.logger import get_logger

logger = get_logger(__name__)
app = create_app()

if __name__ == "__main__":
    try:
        from app import LineBotApp
        logger.info("啟動 LineBot 應用程式...")
        bot_app = LineBotApp()
        bot_app.run()
        logger.info("LineBot 應用程式已停止。")
    except Exception:
        logger.exception("應用程式啟動失敗。"); raise
    finally:
        logger.info("LineBot 應用程式主執行緒已完成執行。")
