"""
應用程式設定模組
負責管理所有環境變數和配置，型別安全、動態驗證。
"""
import os
import json
from typing import Optional, Type, TypeVar, Any, Dict, Union, get_args, get_origin
from dataclasses import dataclass, fields, MISSING

T = TypeVar("T")

def _get_config_value(
    key: str, target_type: Type[T], default: Optional[T] = None, required: bool = True
) -> T:
    """
    從環境變數取得配置值，處理型別轉換、預設值和必要性。
    """
    value = os.getenv(key)
    if value is None:
        if required:
            raise ValueError(f"Required environment variable '{key}' is not set.")
        return default

    origin_type = get_origin(target_type)
    if origin_type is Union:
        underlying_types = [t for t in get_args(target_type) if t is not type(None)]
        actual_type = underlying_types[0] if underlying_types else str
    else:
        actual_type = target_type

    try:
        if actual_type is bool:
            return value.lower() in ("true", "1", "yes")
        if actual_type is str:
            return value
        return actual_type(value)
    except (ValueError, TypeError):
        raise ValueError(
            f"Environment variable '{key}' has an invalid value '{value}' for type {actual_type.__name__}."
        )

@dataclass
class AppConfig:
    """
    應用程式配置類別。
    所有環境變數與預設值型別安全管理。
    """
    # LINE Bot 設定
    line_channel_secret: str
    line_channel_access_token: str
    # GCP 設定 (gcp_service_account_json 設為可選，因為我們會從檔案路徑讀取)
    gcp_service_account_json: Optional[str]
    gcp_project_id: str
    # Cloudinary 設定
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    # 有預設值的參數
    gcp_location: str = "us-central1"
    redis_url: Optional[str] = None
    port: int = 10000
    debug: bool = False
    text_model_name: str = "gemini-2.5-flash"
    image_model_name: str = "imagen-3.0-generate-002" # 注意：這應為 imagen-3.0-generate-002 等具體模型
    chat_history_ttl: int = 7200
    max_chat_history_length: int = 20
    nearby_query_ttl: int = 300
    max_search_results: int = 5
    search_radius_km: int = 2

def load_config() -> AppConfig:
    """
    從環境變數動態載入應用程式配置，並進行驗證。
    會根據 GOOGLE_APPLICATION_CREDENTIALS (本地) 或 GCP_SERVICE_ACCOUNT_JSON (Render) 來載入 GCP 金鑰。
    """
    try:
        kwargs: Dict[str, Any] = {}
        # 先讀取所有非 GCP 金鑰的設定
        for field in fields(AppConfig):
            if field.name in ["gcp_project_id", "gcp_service_account_json"]:
                continue
            env_key = field.name.upper()
            has_default = field.default is not MISSING or field.default_factory is not MISSING
            kwargs[field.name] = _get_config_value(
                key=env_key,
                target_type=field.type,
                default=field.default if has_default else None,
                required=not has_default
            )

        # 智慧地處理 GCP 金鑰
        gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        gcp_json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON")

        if gcp_credentials_path:
            # 本地端開發模式：從檔案路徑讀取
            print(f"Loading GCP credentials from file: {gcp_credentials_path}")
            with open(gcp_credentials_path, 'r') as f:
                gcp_info = json.load(f)
            kwargs["gcp_service_account_json"] = json.dumps(gcp_info) # 將讀取的內容存入 config
        elif gcp_json_str:
            # Render 部署模式：從環境變數讀取
            print("Loading GCP credentials from environment variable string.")
            gcp_info = json.loads(gcp_json_str)
            kwargs["gcp_service_account_json"] = gcp_json_str
        else:
            raise ValueError("Neither GOOGLE_APPLICATION_CREDENTIALS nor GCP_SERVICE_ACCOUNT_JSON is set.")

        # 從解析後的 JSON 中取得 project_id
        project_id = gcp_info.get("project_id")
        if not project_id:
            raise ValueError("'project_id' not found in GCP service account credentials.")
        kwargs["gcp_project_id"] = project_id
        
        return AppConfig(**kwargs)
        
    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during configuration loading: {e}") from e