"""
快取服務模組
優化 Render 平台效能
"""
import json
import time
from typing import Optional, Any, Dict
from functools import wraps

from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryCache:
    """記憶體快取實作（當 Redis 不可用時使用）"""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[str]:
        """取得快取值"""
        if key in self._cache:
            item = self._cache[key]
            if time.time() < item['expires']:
                return item['value']
            else:
                del self._cache[key]
        return None
    
    def set(self, key: str, value: str, ex: int = 300) -> bool:
        """設定快取值"""
        try:
            # 如果快取已滿，移除最舊的項目
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), 
                               key=lambda k: self._cache[k]['created'])
                del self._cache[oldest_key]
            
            self._cache[key] = {
                'value': value,
                'expires': time.time() + ex,
                'created': time.time()
            }
            return True
        except Exception as e:
            logger.error(f"Memory cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """刪除快取值"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False


def cache_response(timeout: int = 300):
    """回應快取裝飾器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = f"response_{func.__name__}_{hash(str(args) + str(kwargs))}"
            
            # 嘗試從快取取得
            # 這裡可以整合 Redis 或記憶體快取
            
            # 如果沒有快取，執行函式並快取結果
            result = func(*args, **kwargs)
            
            return result
        return wrapper
    return decorator