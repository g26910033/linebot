"""
Render 平台專用設定
優化部署效能和資源使用

此模組提供針對 Render.com 雲平台優化的配置。
主要關注 Gunicorn 服務器參數、記憶體管理和快取策略，
以確保應用在高負載下仍能穩定運行並有效利用資源。
"""
import os
import logging
from .settings import AppConfig, load_config

# 設定日誌記錄器
logger = logging.getLogger(__name__)

class RenderConfig(AppConfig):
    """Render 平台優化配置。

    此類別擴展了基礎的 AppConfig，並覆蓋或添加了針對 Render
    部署環境的特定優化參數。所有重要參數均可通過環境變數進行調整。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Helper function to get environment variables with type conversion and error handling
        def _get_env(key: str, default_value, type_func=str):
            """從環境變數獲取值，並嘗試轉換為指定類型。"""
            env_val = os.environ.get(key)
            if env_val is not None:
                try:
                    return type_func(env_val)
                except ValueError:
                    logger.warning(
                        f"配置錯誤: 環境變數 '{key}' 的值 '{env_val}' 無法轉換為 {type_func.__name__}。"
                        f" 將使用預設值: {default_value}"
                    )
                    return default_value
            return default_value

        # --- Gunicorn 服務器配置優化 ---
        # Gunicorn worker 數量：根據 CPU 核數計算，並可通過環境變數覆蓋
        # 建議為 (2 * CPU_COUNT) + 1，但對於資源有限的雲平台，會採取更保守的策略
        self.gunicorn_workers: int = _get_env("GUNICORN_WORKERS", self._calculate_workers(), int)
        # Gunicorn worker 超時時間，單位：秒。防止請求長時間卡住，導致 worker 無響應
        self.gunicorn_timeout: int = _get_env("GUNICORN_TIMEOUT", 120, int)
        # 保持連接活動時間，單位：秒。減少連接建立開銷，提高效率，尤其適用於頻繁短連接
        self.gunicorn_keepalive: int = _get_env("GUNICORN_KEEPALIVE", 5, int)
        # worker 處理的最大請求數，達到後會自動重啟以釋放記憶體，避免記憶體洩漏
        self.max_requests: int = _get_env("GUNICORN_MAX_REQUESTS", 1000, int)
        # max_requests 的抖動範圍，防止所有 worker 同時重啟，影響服務穩定性
        self.max_requests_jitter: int = _get_env("GUNICORN_MAX_REQUESTS_JITTER", 100, int)
        # Gunicorn worker 進程使用的線程數。適合 I/O 密集型應用，可提高併發處理能力
        self.gunicorn_threads: int = _get_env("GUNICORN_THREADS", 1, int)
        # Gunicorn worker 類別 (e.g., 'sync', 'gevent', 'uvloop')
        # 'sync' 是預設且最穩定的。使用 'gevent'/'uvloop' 需要額外安裝異步 I/O 庫。
        self.gunicorn_worker_class: str = _get_env("GUNICORN_WORKER_CLASS", "sync", str)
        # Gunicorn 綁定地址，顯式綁定到 Render 提供的端口。'0.0.0.0' 表示監聽所有網絡接口。
        self.gunicorn_bind: str = f"0.0.0.0:{_get_env('PORT', '8000', int)}"
        # 設定 Gunicorn 日誌級別 (可選：debug, info, warning, error, critical)。
        # info 級別通常足以用於生產環境。
        self.gunicorn_log_level: str = _get_env("GUNICORN_LOG_LEVEL", "info", str)

        # --- 應用程式級記憶體和性能優化 ---
        # 對話歷史在記憶體中的存活時間，單位：秒 (預設 1 小時)。
        # 過期後可被清理，減少記憶體佔用。
        self.chat_history_ttl: int = _get_env("CHAT_HISTORY_TTL", 3600, int)
        # 限制對話歷史的單次請求最大長度，防止記憶體無限增長。
        self.max_chat_history_length: int = _get_env("MAX_CHAT_HISTORY_LENGTH", 10, int)

        # --- 快取優化 ---
        # 是否啟用回應快取，減少重複計算和數據庫查詢，提高響應速度。
        # 建議在讀取頻繁但數據不經常變化的端點啟用。
        self.enable_response_cache: bool = _get_env("ENABLE_RESPONSE_CACHE", True, lambda x: x.lower() == 'true')
        # 回應快取時間，單位：秒 (預設 5 分鐘)。
        # 快取失效後，會重新生成回應。
        self.cache_timeout: int = _get_env("CACHE_TIMEOUT", 300, int)

    def _calculate_workers(self) -> int:
        """根據可用 CPU 計算最佳 Gunicorn worker 數量。

        雲平台 (如 Render) 的資源配置通常較為有限，為避免記憶體不足 (OOM) 問題，
        此方法採取較為保守的策略。它會計算 CPU 核數，並將 worker 數量
        限制在一個合理的範圍 (最小 1 個，最多 4 個)，以適應大多數 Render 服務方案。
        此值可通過環境變數 `GUNICORN_WORKERS` 覆蓋。
        """
        try:
            # 獲取 CPU 核數，如果無法獲取則預設為 1
            cpu_count = os.cpu_count() or 1
            # 考慮 Render 的不同服務方案 (Starter: 1 CPU, Standard: 2 CPU, Pro: 4+ CPU)
            # 將 worker 數量限制在 1 到 4 之間，這被認為是在 Render 上穩定運行的安全範圍。
            # 如果 cpu_count=1, max(1,1)=1, min(1,4)=1.
            # 如果 cpu_count=2, max(2,1)=2, min(2,4)=2.
            # 如果 cpu_count=4, max(4,1)=4, min(4,4)=4.
            # 如果 cpu_count>4, min(cpu_count, 4)=4.
            return min(max(cpu_count, 1), 4)
        except Exception as e:
            logger.error(f"計算 Gunicorn worker 數量時發生錯誤，將使用預設值 2: {e}")
            return 2  # 發生錯誤時的預設值


def load_render_config() -> RenderConfig:
    """載入 Render 優化配置。

    首先載入基礎應用配置 (AppConfig)，然後將其屬性傳遞給 RenderConfig
    構造函數。這使得 RenderConfig 能夠在基礎配置之上，進行平台特定的
    優化和覆蓋，確保所有配置項都得到正確處理。
    """
    base_config = load_config()
    # 將 base_config 的所有屬性作為關鍵字參數傳遞給 RenderConfig 構造函數。
    # 這樣 RenderConfig 就能繼承 AppConfig 的所有設定，並在此基礎上進行覆寫。
    return RenderConfig(**base_config.__dict__)