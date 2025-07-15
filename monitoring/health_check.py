
"""
健康檢查和監控模組
提供系統資源、服務狀態監控，優化 Render 平台監控。
"""
import time
import psutil
from typing import Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class HealthChecker:
    """
    健康檢查器。
    提供系統資源、服務狀態查詢，支援 Render 平台監控。
    """
    def __init__(self) -> None:
        self.start_time: float = time.time()

    def get_health_status(self) -> Dict[str, Any]:
        """
        取得詳細健康狀態。
        Returns:
            Dict[str, Any]: 健康狀態資訊。
        """
        current_time: float = time.time()
        try:
            system_info: Dict[str, Any] = self._get_system_info()
            services_info: Dict[str, bool] = self._check_services()
            logger.debug("[HealthChecker] Health status OK. uptime=%.2fs", current_time - self.start_time)
            return {
                "status": "healthy",
                "timestamp": current_time,
                "uptime": current_time - self.start_time,
                "system": system_info,
                "services": services_info,
            }
        except Exception as e:
            logger.exception("[HealthChecker] Health check failed.")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": current_time,
            }

    def _get_system_info(self) -> Dict[str, Any]:
        """
        取得系統資訊。
        Returns:
            Dict[str, Any]: CPU、記憶體、磁碟使用率。
        """
        try:
            cpu: float = psutil.cpu_percent()
            mem: float = psutil.virtual_memory().percent
            disk: float = psutil.disk_usage('/').percent
            logger.debug("[HealthChecker] System info: cpu=%.1f%% mem=%.1f%% disk=%.1f%%", cpu, mem, disk)
            return {
                "cpu_percent": cpu,
                "memory_percent": mem,
                "disk_percent": disk,
            }
        except Exception as e:
            logger.exception("[HealthChecker] Error getting system info.")
            return {"error": f"Unable to get system info: {e}"}

    def _check_services(self) -> Dict[str, bool]:
        """
        檢查服務狀態。
        Returns:
            Dict[str, bool]: 各服務狀態。
        """
        services: Dict[str, bool] = {}
        
        # 檢查 Redis 連線
        try:
            import redis
            from config.settings import load_config
            config = load_config()
            if config.redis_url:
                redis_client = redis.from_url(config.redis_url)
                redis_client.ping()
                services["redis"] = True
            else:
                services["redis"] = False
        except Exception:
            services["redis"] = False
        
        # 檢查 Vertex AI 可用性
        try:
            import vertexai
            services["vertex_ai"] = True
        except Exception:
            services["vertex_ai"] = False
            
        # 檢查 Cloudinary 配置
        try:
            import cloudinary
            services["cloudinary"] = True
        except Exception:
            services["cloudinary"] = False
            
        logger.debug("[HealthChecker] Service status: %s", services)
        return services


# 全域健康檢查器實例
health_checker: HealthChecker = HealthChecker()
