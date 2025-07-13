"""
Render 平台專用設定
優化部署效能和資源使用
"""
import os
from .settings import AppConfig, load_config


class RenderConfig(AppConfig):
    """Render 平台優化配置"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Render 平台特定優化
        self.gunicorn_workers = self._calculate_workers()
        self.gunicorn_timeout = 120
        self.gunicorn_keepalive = 2
        self.max_requests = 1000
        self.max_requests_jitter = 100
        
        # 記憶體優化
        self.chat_history_ttl = 3600  # 減少到 1 小時
        self.max_chat_history_length = 10  # 限制對話歷史長度
        
        # 快取優化
        self.enable_response_cache = True
        self.cache_timeout = 300  # 5 分鐘快取
    
    def _calculate_workers(self) -> int:
        """根據可用 CPU 計算最佳 worker 數量"""
        try:
            cpu_count = os.cpu_count() or 1
            # Render Starter: 1 CPU, Standard: 2 CPU, Pro: 4+ CPU
            return min(max(cpu_count, 1), 4)  # 最少 1 個，最多 4 個
        except:
            return 2  # 預設值


def load_render_config() -> RenderConfig:
    """載入 Render 優化配置"""
    base_config = load_config()
    return RenderConfig(**base_config.__dict__)