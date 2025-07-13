"""
應用程式設定模組
負責管理所有環境變數和配置
"""
import os
import json
from typing import Optional, Type, TypeVar
from dataclasses import dataclass, fields, MISSING

T = TypeVar("T")


def _get_config_value(
    key: str, target_type: Type[T] = str, default: Optional[T] = None, required: bool = True
) -> T:
    """
    從環境變數取得配置值，處理型別轉換、預設值和必要性。

    Args:
        key (str): 環境變數的鍵名。
        target_type (Type[T]): 值的目標型別 (例如：int, bool, str)。
        default (Optional[T]): 如果環境變數未設定且 required 為 False 時使用的預設值。
        required (bool): 若為 True，則當環境變數未設定時會拋出 ValueError。

    Returns:
        T: 配置值。

    Raises:
        ValueError: 當必要變數遺失，或型別轉換失敗時。
    """
    value = os.getenv(key)

    if value is None:
        if required:
            raise ValueError(f"Required environment variable '{key}' is not set.")
        return default

    try:
        if target_type is bool:
            # 特殊處理布林值：'true', '1', 'yes' 視為 True，其他為 False
            return value.lower() in ("true", "1", "yes")
        return target_type(value)
    except ValueError:
        raise ValueError(
            f"Environment variable '{key}' has an invalid value '{value}' "
            f"for type {target_type.__name__}."
        )


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
    image_model_name: str = "imagen-3.0"

    # 快取設定
    chat_history_ttl: int = 7200  # 2小時
    nearby_query_ttl: int = 300  # 5分鐘

    # 搜尋設定
    max_search_results: int = 5
    search_radius_km: int = 2


def load_config() -> AppConfig:
    """載入應用程式配置"""
    try:
        # Pre-map dataclass fields for efficient lookup
        app_config_fields = {f.name: f for f in fields(AppConfig)}

        # Create a dictionary to hold the loaded config values
        # This allows us to use dataclass.__init__(**kwargs) at the end
        loaded_values = {}

        # Helper to get value for a specific field, considering its dataclass default
        def _get_field_env_value(field_name: str):
            field_obj: Field = app_config_fields.get(field_name)
            if not field_obj:
                raise AttributeError(f"Field '{field_name}' not found in AppConfig.")

            env_var_key = field_name.upper()

            # Determine if the field has a default value in the dataclass
            has_default = field_obj.default is not MISSING or field_obj.default_factory is not MISSING
            default_value = field_obj.default if has_default else None
            required = not has_default

            try:
                # Call the common helper to get the value from environment
                return _get_config_value(
                    env_var_key, target_type=field_obj.type, default=default_value, required=required
                )
            except ValueError as e:
                # Add context to the error message for easier debugging
                raise ValueError(
                    f"Failed to load environment variable '{env_var_key}' for field '{field_name}': {e}"
                ) from e

        # LINE Bot 設定
        loaded_values["line_channel_secret"] = _get_field_env_value("line_channel_secret")
        loaded_values["line_channel_access_token"] = _get_field_env_value("line_channel_access_token")

        # GCP 設定 (special handling for project_id derived from JSON)
        # GCP_SERVICE_ACCOUNT_JSON is required and does not have a default in AppConfig
        gcp_service_account_json_str = _get_field_env_value("gcp_service_account_json")
        try:
            gcp_info = json.loads(gcp_service_account_json_str)
        except json.JSONDecodeError:
            raise ValueError(
                f"GCP_SERVICE_ACCOUNT_JSON is not a valid JSON string. Raw value starts with: '
                {gcp_service_account_json_str[:50]}...'
            ")

        gcp_project_id = gcp_info.get("project_id")
        if not gcp_project_id:
            raise ValueError("'project_id' is missing or empty in parsed GCP_SERVICE_ACCOUNT_JSON.")
        
        loaded_values["gcp_service_account_json"] = gcp_service_account_json_str
        loaded_values["gcp_project_id"] = gcp_project_id
        
        # GCP_LOCATION has a default in AppConfig, so it's not strictly required in ENV
        loaded_values["gcp_location"] = _get_field_env_value("gcp_location")

        # Cloudinary 設定
        loaded_values["cloudinary_cloud_name"] = _get_field_env_value("cloudinary_cloud_name")
        loaded_values["cloudinary_api_key"] = _get_field_env_value("cloudinary_api_key")
        loaded_values["cloudinary_api_secret"] = _get_field_env_value("cloudinary_api_secret")

        # Redis 設定 (Optional, has default of None in AppConfig)
        loaded_values["redis_url"] = _get_field_env_value("redis_url")

        # 應用程式設定 (have defaults in AppConfig)
        loaded_values["port"] = _get_field_env_value("port")
        loaded_values["debug"] = _get_field_env_value("debug")

        # AI 模型設定 (have defaults in AppConfig)
        loaded_values["text_model_name"] = _get_field_env_value("text_model_name")
        loaded_values["image_model_name"] = _get_field_env_value("image_model_name")
        
        # The remaining fields (chat_history_ttl, nearby_query_ttl, max_search_results, search_radius_km)
        # are not explicitly loaded from environment variables in the original logic.
        # They rely solely on their default values defined in the AppConfig dataclass.
        # Therefore, they are not added to 'loaded_values' and will automatically take their defaults
        # when the AppConfig instance is created.

        return AppConfig(**loaded_values)

    except ValueError as e:
        # Catch specific ValueErrors that indicate configuration issues
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during configuration loading
        raise RuntimeError(f"An unexpected error occurred during configuration loading: {e}") from e
