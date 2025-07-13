
"""
Render 平台專用設定
優化部署效能和資源使用

此模組提供針對 Render.com 雲平台優化的配置。
主要關注 Gunicorn 服務器參數、記憶體管理和快取策略，
以確保應用在高負載下仍能穩定運行並有效利用資源。
"""
import os
import logging
from typing import Any, Callable
from .settings import AppConfig, load_config

logger = logging.getLogger(__name__)


class RenderConfig(AppConfig):
    """
    Render 平台優化配置。

    擴展基礎 AppConfig，並覆蓋/新增 Render 部署環境的特定優化參數。
    所有重要參數均可通過環境變數進行調整。
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        def _get_env(key: str, default_value: Any, type_func: Callable = str) -> Any:
            """
            從環境變數獲取值，並嘗試轉換為指定類型。
            Args:
                key (str): 環境變數名稱。
                default_value (Any): 預設值。
                type_func (Callable): 轉換型別函式。
            Returns:
                Any: 轉換後的值或預設值。
            """
            env_val = os.environ.get(key)
            if env_val is not None:
                try:
                    return type_func(env_val)
                except Exception as e:
                    logger.warning(
                        f"配置錯誤: 環境變數 '{key}' 的值 '{env_val}' 無法轉換為 {type_func.__name__}。"
                        f" 將使用預設值: {default_value} ({e})"
                    )
            return default_value

        # --- Gunicorn 服務器配置優化 ---
        self.gunicorn_workers: int = _get_env("GUNICORN_WORKERS", self._calculate_workers(), int)
        self.gunicorn_timeout: int = _get_env("GUNICORN_TIMEOUT", 120, int)
        self.gunicorn_keepalive: int = _get_env("GUNICORN_KEEPALIVE", 5, int)
        self.max_requests: int = _get_env("GUNICORN_MAX_REQUESTS", 1000, int)
        self.max_requests_jitter: int = _get_env("GUNICORN_MAX_REQUESTS_JITTER", 100, int)
        self.gunicorn_threads: int = _get_env("GUNICORN_THREADS", 1, int)
        self.gunicorn_worker_class: str = _get_env("GUNICORN_WORKER_CLASS", "sync", str)
        self.gunicorn_bind: str = f"0.0.0.0:{_get_env('PORT', '8000', int)}"
        self.gunicorn_log_level: str = _get_env("GUNICORN_LOG_LEVEL", "info", str)

        # --- 應用程式級記憶體和性能優化 ---
        self.chat_history_ttl: int = _get_env("CHAT_HISTORY_TTL", 3600, int)
        self.max_chat_history_length: int = _get_env("MAX_CHAT_HISTORY_LENGTH", 10, int)

        # --- 快取優化 ---
        self.enable_response_cache: bool = _get_env("ENABLE_RESPONSE_CACHE", True, lambda x: str(x).lower() == 'true')
        self.cache_timeout: int = _get_env("CACHE_TIMEOUT", 300, int)


    def _calculate_workers(self) -> int:
        """
        根據可用 CPU 計算最佳 Gunicorn worker 數量。
        雲平台 (如 Render) 的資源配置通常較有限，為避免 OOM 問題，
        採取保守策略，worker 數量限制在 1~4。
        Returns:
            int: 建議的 worker 數量。
        """
        try:
            cpu_count: int = os.cpu_count() or 1
            return min(max(cpu_count, 1), 4)
        except Exception as e:
            logger.error(f"計算 Gunicorn worker 數量時發生錯誤，將使用預設值 2: {e}")
            return 2



def load_render_config() -> RenderConfig:
    """
    載入 Render 優化配置。
    先載入基礎 AppConfig，再傳遞給 RenderConfig 進行平台特定優化。
    Returns:
        RenderConfig: Render 平台優化配置實例。
    """
    base_config = load_config()
    return RenderConfig(**base_config.__dict__)