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
    """從環境變數動態載入應用程式配置，並進行驗證。"""
    try:
        kwargs = {}
        # 遍歷 AppConfig 的所有欄位來動態載入配置
        for field in fields(AppConfig):
            # gcp_project_id 是特殊情況，它從 gcp_service_account_json 衍生而來
            if field.name == "gcp_project_id":
                continue

            # 確定環境變數的鍵名和預設值
            env_key = field.name.upper()
            has_default = field.default is not MISSING or field.default_factory is not MISSING
            
            # 使用輔助函數獲取並驗證值
            kwargs[field.name] = _get_config_value(
                key=env_key,
                target_type=field.type,
                default=field.default if has_default else None,
                required=not has_default
            )

        # 特殊處理：從服務帳號 JSON 中解析 project_id
        gcp_json_str = kwargs.get("gcp_service_account_json")
        if not gcp_json_str:
            # 如果 gcp_service_account_json 是必需的，_get_config_value 應該已經拋出錯誤
            # 但為了代碼清晰，這裡可以再次確認
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
        # Catch specific ValueErrors that indicate configuration issues
        raise RuntimeError(f"Configuration error: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during configuration loading
        raise RuntimeError(f"An unexpected error occurred during configuration loading: {e}") from e
