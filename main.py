    """
主程式入口點
保持向後相容性
"""
from app import create_app
from utils.logger import get_logger

# 取得日誌記錄器實例
logger = get_logger(__name__)

# 建立應用程式實例
# 此行通常用於WSGI伺服器（例如Gunicorn）載入'app'物件。
# 它是無條件執行的，以確保當main.py被匯入時'app'是可用的。
app = create_app()

if __name__ == "__main__":
    # 此區塊在main.py被直接執行時運行。
    try:
        from app import LineBotApp # 延遲匯入 LineBotApp 以優化 Web 伺服器啟動時間
        logger.info("啟動 LineBot 應用程式...")
        bot_app = LineBotApp()
        bot_app.run()
        logger.info("LineBot 應用程式已停止。") # 此行可能在bot.run()阻塞時不會被觸及，但會在正常停止時記錄
    except Exception as e:
        # 使用 logger.exception() 自動記錄錯誤堆疊追蹤
        logger.exception(f"應用程式啟動失敗: {e}")
        # 重新拋出異常以便上層系統（如容器編排器）能偵測到啟動失敗
        raise
    finally:
        # 此區塊會確保無論成功或失敗（在重新拋出異常之前），都會記錄一條日誌訊息。
        # 它清晰地表明了主程式中機器人應用的執行路徑已結束。
        logger.info("LineBot 應用程式主執行緒已完成執行。")
