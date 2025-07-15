"""
應用程式設定模組
負責管理所有環境變數和配置，型別安全、動態驗證。
"""
import os
import json
from typing import (Optional, Type, TypeVar, Any, Dict, Union,
                    get_args, get_origin)
from dataclasses import dataclass, fields, MISSING

T = TypeVar("T")


def _get_config_value(
        key: str,
        target_type: Type[T],
        default: Optional[T] = None,
        required: bool = True) -> Optional[T]:
    """
    從環境變數取得配置值，處理型別轉換、預設值和必要性。
    """
    value = os.getenv(key)
    if value is None:
        if required and default is None:
            raise ValueError(
                f"Required environment variable '{key}' is not set.")
        return default

    origin_type = get_origin(target_type)
    # 處理 Optional[T] (即 Union[T, None])
    if origin_type is Union and type(None) in get_args(target_type):
        # 取得 T 的實際型別
        actual_type = next(
            (t for t in get_args(target_type) if t is not type(None)), str)
    else:
        actual_type = target_type

    try:
        if actual_type is bool:
            return value.lower() in ("true", "1", "yes")
        if actual_type is str:
            return value
        # 對於其他型別，例如 int, float
        return actual_type(value)
    except (ValueError, TypeError):
        raise ValueError(
            f"Environment variable '{key}' has an invalid value '{value}' "
            f"for type {actual_type.__name__}.")


@dataclass
class AppConfig:
    """
    應用程式配置類別。
    所有環境變數與預設值型別安全管理。
    """
    # --- 必要欄位 (無預設值) ---
    # LINE Bot 設定
    line_channel_secret: str
    line_channel_access_token: str
    # GCP 設定
    gcp_project_id: str
    gcp_service_account_json: str
    # Cloudinary 設定
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    # API 金鑰
    openweather_api_key: str
    news_api_key: str

    # --- 可選/有預設值的欄位 ---
    # GCP 設定
    gcp_location: str = "us-central1"
    # API 金鑰
    finnhub_api_key: Optional[str] = None
    # 應用程式行為設定
    redis_url: Optional[str] = None
    port: int = 10000
    debug: bool = False
    text_model_name: str = "gemini-2.5-flash"
    image_model_name: str = "imagen-3.0-generate-002"
    chat_history_ttl: int = 7200
    max_chat_history_length: int = 20
    nearby_query_ttl: int = 300
    max_search_results: int = 5
    search_radius_km: int = 2


def _load_gcp_credentials() -> Dict[str, str]:
    """
    智慧地載入 GCP 憑證，支援本地端檔案和 Render 環境變數。
    優化安全性和錯誤處理。
    """
    gcp_credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    gcp_json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON")

    gcp_info = {}
    service_account_json = ""

    try:
        if gcp_credentials_path:
            print(f"Loading GCP credentials from file: {gcp_credentials_path}")
            with open(gcp_credentials_path, 'r', encoding='utf-8') as f:
                gcp_info = json.load(f)
            service_account_json = json.dumps(gcp_info)
        elif gcp_json_str:
            print("Loading GCP credentials from environment variable.")
            # 驗證 JSON 格式
            gcp_info = json.loads(gcp_json_str)
            service_account_json = gcp_json_str
        else:
            raise ValueError(
                "Neither GOOGLE_APPLICATION_CREDENTIALS nor "
                "GCP_SERVICE_ACCOUNT_JSON is set.")

        # 驗證必要欄位
        required_fields = ["type", "project_id", "private_key_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if not gcp_info.get(field)]
        
        if missing_fields:
            raise ValueError(f"Missing required fields in GCP credentials: {missing_fields}")

        project_id = gcp_info.get("project_id")
        client_email = gcp_info.get("client_email")
        
        print(f"GCP credentials loaded successfully for project: {project_id}")
        print(f"Service account: {client_email}")

        return {
            "gcp_project_id": project_id,
            "gcp_service_account_json": service_account_json
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in GCP credentials: {e}")
    except Exception as e:
        raise ValueError(f"Error loading GCP credentials: {e}")


def load_config() -> AppConfig:
    """
    從環境變數動態載入應用程式配置，並進行驗證。
    """
    print("--- Loading Application Configuration ---")
    try:
        kwargs: Dict[str, Any] = {}

        # 載入 GCP 憑證
        gcp_creds = _load_gcp_credentials()
        kwargs.update(gcp_creds)

        # 載入其餘設定
        for field in fields(AppConfig):
            if field.name in kwargs:  # 跳過已處理的 GCP 欄位
                continue

            env_key = field.name.upper()
            is_optional = (
                get_origin(field.type) is Union and
                type(None) in get_args(field.type)
            )
            has_default = (field.default is not MISSING or
                           field.default_factory is not MISSING)

            value = _get_config_value(
                key=env_key,
                target_type=field.type,
                default=field.default if has_default else None,
                required=not (is_optional or has_default)
            )
            kwargs[field.name] = value
            # 安全地記錄載入的設定值
            log_value = "********" if "key" in field.name.lower() or "secret" in field.name.lower() or "token" in field.name.lower() else value
            print(f"  - Loaded '{field.name}': {log_value}")

        print("--- Configuration Loading Complete ---")
        return AppConfig(**kwargs)

    except (ValueError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        raise RuntimeError(
            "An unexpected error occurred during configuration loading: "
            f"{e}") from e
