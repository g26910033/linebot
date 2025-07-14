# scripts/setup_rich_menu.py
import os
import sys
import json

# 將專案根目錄添加到 Python 路徑中，以便能夠匯入其他模組
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, RichMenuRequest,
    ApiException)
from config.settings import load_config
from utils.logger import get_logger, setup_root_logger

# 設定日誌
setup_root_logger()
logger = get_logger(__name__)

def setup_rich_menu():
    """
    一個獨立的腳本，專門用來設定 LINE Bot 的預設圖文選單。
    """
    rich_menu_name = "Default Rich Menu"
    logger.info("--- Starting Standalone Rich Menu Setup ---")
    
    try:
        config = load_config()
        configuration = Configuration(access_token=config.line_channel_access_token)

        # 確保路徑是相對於此腳本的位置
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, 'rich_menu.json')
        png_path = os.path.join(base_dir, 'rich_menu_background.png')

        if not os.path.exists(json_path) or not os.path.exists(png_path):
            logger.error(f"Rich menu files not found. JSON: {json_path}, PNG: {png_path}")
            sys.exit(1)

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # 1. 刪除舊選單
            logger.info("Step 1: Deleting old rich menus...")
            rich_menu_list = line_bot_api.get_rich_menu_list()
            for menu in rich_menu_list.richmenus:
                if menu.name == rich_menu_name:
                    logger.info(f"Deleting old menu: {menu.rich_menu_id}")
                    line_bot_api.delete_rich_menu(menu.rich_menu_id)
            logger.info("Step 1 finished.")

            # 2. 建立新選單
            logger.info("Step 2: Creating new rich menu...")
            with open(json_path, 'r', encoding='utf-8') as f:
                rich_menu_json = json.load(f)
            rich_menu_json['name'] = rich_menu_name
            rich_menu_to_create = RichMenuRequest.from_dict(rich_menu_json)
            rich_menu_id_response = line_bot_api.create_rich_menu(rich_menu_request=rich_menu_to_create)
            rich_menu_id = rich_menu_id_response.rich_menu_id
            logger.info(f"Step 2 finished. New menu ID: {rich_menu_id}")

            # 3. 上傳圖片
            logger.info(f"Step 3: Uploading image for menu ID: {rich_menu_id}")
            with open(png_path, 'rb') as f:
                line_bot_api.upload_rich_menu_image(
                    rich_menu_id=rich_menu_id,
                    body=f.read(),
                    _headers={'Content-Type': 'image/png'}
                )
            logger.info("Step 3 finished. Image uploaded.")

            # 4. 設為預設
            logger.info(f"Step 4: Setting menu {rich_menu_id} as default...")
            line_bot_api.set_default_rich_menu(rich_menu_id)
            logger.info("Step 4 finished. Menu set as default.")

        logger.info("--- Standalone Rich Menu Setup Successfully Completed ---")

    except ApiException as e:
        logger.error(f"LINE API Error during rich menu setup: {e}", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during rich menu setup: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    setup_rich_menu()
