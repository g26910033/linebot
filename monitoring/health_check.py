    """
健康檢查和監控模組
優化 Render 平台監控
"""
import time
import psutil
from typing import Dict, Any

from utils.logger import get_logger

logger = get_logger(__name__)


class HealthChecker:
    """健康檢查器"""

    def __init__(self):
        self.start_time = time.time()

    def get_health_status(self) -> Dict[str, Any]:
        """取得詳細健康狀態"""
        current_time = time.time()  # 獲取一次當前時間以確保時間戳和運行時間的一致性
        try:
            return {
                "status": "healthy",
                "timestamp": current_time,
                "uptime": current_time - self.start_time,
                "system": self._get_system_info(),
                "services": self._check_services(),
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": current_time,
            }

    def _get_system_info(self) -> Dict[str, Any]:
        """取得系統資訊"""
        try:
            # psutil.cpu_percent() 在無 interval 參數時是非阻塞的，會計算自上次呼叫以來的 CPU 使用率。
            # 這樣可以避免健康檢查阻塞，使其更快速響應。
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
            }
        except Exception as e:  # 捕獲具體異常並記錄
            logger.error(f"Error getting system info: {e}")
            return {"error": f"Unable to get system info: {e}"}

    def _check_services(self) -> Dict[str, bool]:
        """檢查服務狀態"""
        # 這裡可以加入實際的服務檢查邏輯，例如檢查資料庫連線、其他微服務的健康端點等。
        # 示例：
        # try:
        #     db_status = self._check_database_connection()
        # except Exception:
        #     db_status = False
        # return {
        #     "database": db_status,
        #     "ai_service": self._check_ai_service_health(),
        # }
        return {
            "ai_service": True,
            "storage_service": True,
            "database": True,
        }


# 全域健康檢查器實例
health_checker = HealthChecker()
