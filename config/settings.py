
"""
應用程式設定模組
負責管理所有環境變數和配置，型別安全、動態驗證。
"""
import os
import json
from typing import Optional, Type, TypeVar, Any, Dict, Union, get_args, get_origin
from dataclasses import dataclass, fields, MISSING, Field

T = TypeVar("T")



def _get_config_value(
    key: str, target_type: Type[T], default: Optional[T] = None, required: bool = True
) -> T:
    """
    從環境變數取得配置值，處理型別轉換、預設值和必要性。
    Args:
        key (str): 環境變數的鍵名。
        target_type (Type[T]): 值的目標型別 (int, bool, str...)。
        default (Optional[T]): 預設值。
        required (bool): 是否必填。
    Returns:
        T: 配置值。
    Raises:
        ValueError: 當必要變數遺失或型別轉換失敗時。
    """
    value = os.getenv(key)
    if value is None:
        if required:
            raise ValueError(f"Required environment variable '{key}' is not set.")
        return default


    # 處理 Optional[T] 型別，提取其內部的基礎型別
    origin_type = get_origin(target_type)
    if origin_type is Union:
        # Optional[T] 實際上是 Union[T, None]
        underlying_types = [t for t in get_args(target_type) if t is not type(None)]
        if underlying_types:
            actual_type = underlying_types[0]
        else:
            actual_type = str
    else:
        actual_type = target_type

    try:
        if actual_type is bool:
            return value.lower() in ("true", "1", "yes")
        # 僅當型別為 str 時直接回傳 value，避免 Optional[str] 轉型錯誤
        if actual_type is str:
            return value
        return actual_type(value)
    except (ValueError, TypeError):
        raise ValueError(
            f"Environment variable '{key}' has an invalid value '{value}' "
            f"for type {actual_type.__name__}."
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
    """
    從環境變數動態載入應用程式配置，並進行驗證。
    Returns:
        AppConfig: 配置物件。
    Raises:
        RuntimeError: 配置錯誤或解析失敗。
    """
    try:
        kwargs: Dict[str, Any] = {}
        for field in fields(AppConfig):
            if field.name == "gcp_project_id":
                continue
            env_key = field.name.upper()
            has_default = field.default is not MISSING or field.default_factory is not MISSING
            kwargs[field.name] = _get_config_value(
                key=env_key,
                target_type=field.type,
                default=field.default if has_default else None,
                required=not has_default
            )
        gcp_json_str = kwargs.get("gcp_service_account_json")
        if not gcp_json_str:
            raise ValueError("GCP_SERVICE_ACCOUNT_JSON is required but was not loaded.")
        try:
            gcp_info = json.loads(gcp_json_str)
            project_id = gcp_info.get("project_id")
            if not project_id:
                raise ValueError("'project_id' not found in GCP_SERVICE_ACCOUNT_JSON.")
            kwargs["gcp_project_id"] = project_id
        except json.JSONDecodeError as e:
            raise ValueError(f"GCP_SERVICE_ACCOUNT_JSON is not valid JSON. Error: {e}") from e
        return AppConfig(**kwargs)
    except ValueError as e:
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        raise RuntimeError(f"An unexpected error occurred during configuration loading: {e}") from e
