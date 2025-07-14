import os
import json
import requests
import sys

def setup_rich_menu():
    """
    Creates a new rich menu, uploads its background image,
    and sets it as the default for all users.
    It reads the access token directly from environment variables.
    """
    channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not channel_access_token:
        print("Error: LINE_CHANNEL_ACCESS_TOKEN environment variable not set.")
        print("Please set it before running the script:")
        print("export LINE_CHANNEL_ACCESS_TOKEN='your_channel_access_token'")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {channel_access_token}",
        "Content-Type": "application/json"
    }

    # 1. Create Rich Menu
    try:
        with open('scripts/rich_menu.json', 'r') as f:
            rich_menu_data = json.load(f)
    except FileNotFoundError:
        print("Error: 'scripts/rich_menu.json' not found.")
        sys.exit(1)

    response = requests.post(
        "https://api.line.me/v2/bot/richmenu",
        headers=headers,
        data=json.dumps(rich_menu_data)
    )

    if response.status_code != 200:
        print(f"Error creating rich menu: {response.status_code} {response.text}")
        sys.exit(1)

    rich_menu_id = response.json()['richMenuId']
    print(f"Rich menu created successfully. ID: {rich_menu_id}")

    # 2. Upload Rich Menu Image
    headers['Content-Type'] = 'image/png'
    try:
        with open('scripts/rich_menu_background.png', 'rb') as f:
            image_data = f.read()
    except FileNotFoundError:
        print("Error: 'scripts/rich_menu_background.png' not found.")
        print("Please run 'python scripts/generate_rich_menu_image.py' first.")
        sys.exit(1)


    upload_response = requests.post(
        f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
        headers=headers,
        data=image_data
    )

    if upload_response.status_code != 200:
        print(f"Error uploading rich menu image: {upload_response.status_code} {upload_response.text}")
        sys.exit(1)

    print("Rich menu image uploaded successfully.")

    # 3. Set as Default Rich Menu
    default_response = requests.post(
        f"https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}",
        headers={"Authorization": f"Bearer {channel_access_token}"}
    )

    if default_response.status_code != 200:
        print(f"Error setting default rich menu: {default_response.status_code} {default_response.text}")
        sys.exit(1)

    print("Rich menu set as default successfully.")

if __name__ == "__main__":
    setup_rich_menu()
