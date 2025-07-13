    """
快取服務模組
優化 Render 平台效能
"""
import json
import time
import collections
from typing import Optional, Any, Dict
from functools import wraps

from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryCache:
    """記憶體快取實作（當 Redis 不可用時使用）"""
    
    def __init__(self, max_size: int = 1000):
        # 使用 OrderedDict 來實現 LRU (Least Recently Used) 策略
        self._cache: collections.OrderedDict[str, Dict[str, Any]] = collections.OrderedDict()
        self._max_size = max_size
    
    def get(self, key: str) -> Optional[str]:
        """取得快取值"""
        if key not in self._cache:
            return None

        item = self._cache[key]
        if time.time() < item['expires']:
            # 將最近使用的項目移到 OrderedDict 的末尾，實現 LRU
            self._cache.move_to_end(key)
            return item['value']
        else:
            # 已過期的項目，從快取中刪除
            del self._cache[key]
            return None
    
    def set(self, key: str, value: str, ex: int = 300) -> bool:
        """設定快取值"""
        try:
            # 如果 key 已存在，先刪除，以便後續重新插入時能移到 OrderedDict 末尾 (LRU 策略)
            if key in self._cache:
                del self._cache[key]

            # 如果快取已滿，移除最舊的項目 (OrderedDict 的第一個)，實現 O(1) 移除
            if len(self._cache) >= self._max_size:
                self._cache.popitem(last=False) # 移除 LRU 中最不常用的 (最舊的)
            
            # 添加新項目或更新項目，並將其置於 OrderedDict 末尾
            self._cache[key] = {
                'value': value,
                'expires': time.time() + ex,
                'created': time.time() # 仍然記錄創建時間，但 LRU 策略主要依賴 OrderedDict 的順序
            }
            return True
        except Exception as e:
            logger.error(f"Memory cache set error for key '{key}': {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """刪除快取值"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False


# 全局記憶體快取實例，供裝飾器使用
# 注意：這是一個進程內部的快取，在多進程/多 worker 環境下，每個進程會有自己的獨立快取。
# 若需跨進程共享，應考慮使用 Redis 等外部快取服務。
_global_memory_cache = MemoryCache()


def cache_response(timeout: int = 300):
    """回應快取裝飾器"
    
    此裝飾器用於快取函式（通常是 API 端點）的回應。
    它會將函式的參數和結果序列化為 JSON 並存儲在記憶體快取中。
    
    Args:
        timeout (int): 快取失效時間 (秒)。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成快取鍵，確保一致性。盡可能使用 JSON 序列化來獲得穩定 hash。
            try:
                # 對 args 和 kwargs 進行排序和 JSON 序列化，以確保 hash 值穩定。
                # 注意：args/kwargs 必須是 JSON 序列化的。
                cache_key_parts = (func.__name__, args, tuple(sorted(kwargs.items())))
                cache_key = f"response_cache:{hash(json.dumps(cache_key_parts, sort_keys=True))}"
            except TypeError:
                logger.warning(
                    f"Warning: Arguments or keyword arguments for '{func.__name__}' are not JSON serializable. "
                    f"Falling back to less robust string hashing. Consider making function arguments JSON-friendly."
                )
                # 容錯處理：如果無法 JSON 序列化，則回退到原始的簡單字符串拼接和 hash
                cache_key = f"response_cache:{func.__name__}:{hash(str(args) + str(kwargs))}"
            except Exception as e:
                logger.error(
                    f"Error generating cache key for '{func.__name__}': {e}. Falling back to simple string hashing."
                )
                cache_key = f"response_cache:{func.__name__}:{hash(str(args) + str(kwargs))}"

            # 嘗試從快取取得
            cached_data = _global_memory_cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for key: {cache_key}")
                try:
                    return json.loads(cached_data)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode cached data for key '{cache_key}': {e}. "
                        f"Deleting corrupted cache entry and re-executing function."
                    )
                    _global_memory_cache.delete(cache_key)
                    # Fall through to execute the function
            else:
                logger.debug(f"Cache miss for key: {cache_key}")

            # 如果沒有快取，執行函式並快取結果
            result = func(*args, **kwargs)

            # 快取結果，假設結果是 JSON 序列化的。如果不是，將不會被快取。
            try:
                _global_memory_cache.set(cache_key, json.dumps(result), ex=timeout)
                logger.debug(f"Cache set for key: {cache_key}")
            except TypeError:
                logger.error(f"Function result for '{func.__name__}' is not JSON serializable. Cannot cache this result.")
            except Exception as e:
                logger.error(f"Error setting cache for key '{cache_key}': {e}")

            return result
        return wrapper
    return decorator