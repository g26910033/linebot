"""
健康檢查和監控模組
優化 Render 平台監控
"""
import time
import psutil
from typing import Dict, Any
from flask import jsonify

from utils.logger import get_logger

logger = get_logger(__name__)


class HealthChecker:
    """健康檢查器"""
    
    def __init__(self):
        self.start_time = time.time()
    
    def get_health_status(self) -> Dict[str, Any]:
        """取得詳細健康狀態"""
        try:
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "uptime": time.time() - self.start_time,
                "system": self._get_system_info(),
                "services": self._check_services()
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """取得系統資訊"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent
            }
        except:
            return {"error": "Unable to get system info"}
    
    def _check_services(self) -> Dict[str, bool]:
        """檢查服務狀態"""
        return {
            "ai_service": True,  # 這裡可以加入實際的服務檢查
            "storage_service": True,
            "database": True
        }


# 全域健康檢查器實例
health_checker = HealthChecker()