"""
主程式入口點
保持向後相容性
"""
from app import create_app

# 建立應用程式實例
app = create_app()

if __name__ == "__main__":
    from app import LineBotApp
    
    try:
        bot_app = LineBotApp()
        bot_app.run()
    except Exception as e:
        print(f"Application startup failed: {e}")
        raise