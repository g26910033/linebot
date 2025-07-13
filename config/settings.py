"""
應用程式設定模組
負責管理所有環境變數和配置
"""
import os
import json
from typing import Optional
from dataclasses import dataclass


@dataclass
class AppConfig:
    """應用程式配置類別"""
    # LINE Bot 設定
    line_channel_secret: str
    line_channel_access_token: str
    
    # GCP 設定
    gcp_service_account_json: str
    gcp_project_id: str
    
    # Cloudinary 設定
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    
    # 有預設值的參數必須放在最後
    gcp_location: str = "us-central1"
    
    # Redis 設定
    redis_url: Optional[str] = None
    
    # 應用程式設定
    port: int = 10000
    debug: bool = False
    
    # AI 模型設定
    text_model_name: str = "gemini-2.5-flash"
    image_model_name: str = "imagen-3.0-generate-002"
    
    # 快取設定
    chat_history_ttl: int = 7200  # 2小時
    nearby_query_ttl: int = 300   # 5分鐘
    
    # 搜尋設定
    max_search_results: int = 5
    search_radius_km: int = 2


def load_config() -> AppConfig:
    """載入應用程式配置"""
    try:
        gcp_json_str = os.getenv('GCP_SERVICE_ACCOUNT_JSON')
        if not gcp_json_str:
            raise ValueError("GCP_SERVICE_ACCOUNT_JSON environment variable is required")
        
        gcp_info = json.loads(gcp_json_str)
        
        return AppConfig(
            line_channel_secret=_get_required_env('LINE_CHANNEL_SECRET'),
            line_channel_access_token=_get_required_env('LINE_CHANNEL_ACCESS_TOKEN'),
            gcp_service_account_json=gcp_json_str,
            gcp_project_id=gcp_info.get('project_id'),
            cloudinary_cloud_name=_get_required_env('CLOUDINARY_CLOUD_NAME'),
            cloudinary_api_key=_get_required_env('CLOUDINARY_API_KEY'),
            cloudinary_api_secret=_get_required_env('CLOUDINARY_API_SECRET'),
            redis_url=os.getenv('REDIS_URL'),
            port=int(os.getenv('PORT', 10000)),
            debug=os.getenv('DEBUG', 'False').lower() == 'true'
        )
    except Exception as e:
        raise RuntimeError(f"Failed to load configuration: {e}")


def _get_required_env(key: str) -> str:
    """取得必要的環境變數"""
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Required environment variable {key} is not set")
    return value