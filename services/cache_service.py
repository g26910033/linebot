"""
快取服務模組
提供記憶體快取（LRU）、回應快取裝飾器，優化 Render 平台效能。
"""
import json
import time
from collections import OrderedDict
from typing import Optional, Any, Dict, Callable
from functools import wraps
from utils.logger import get_logger

logger = get_logger(__name__)


class MemoryCache:
    """
    記憶體快取實作（當 Redis 不可用時使用）。
    採用 LRU (Least Recently Used) 策略，最大容量可自訂。
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_size: int = max_size

    def get(self, key: str) -> Optional[str]:
        """
        取得快取值。
        Args:
            key (str): 快取鍵。
        Returns:
            Optional[str]: 快取值或 None。
        """
        item = self._cache.get(key)
        if not item:
            logger.debug("[MemoryCache] Miss for key: %s", key)
            return None
        if time.time() < item['expires']:
            self._cache.move_to_end(key)
            logger.debug("[MemoryCache] Hit for key: %s", key)
            return item['value']
        del self._cache[key]
        logger.info("[MemoryCache] Expired key removed: %s", key)
        return None

    def set(self, key: str, value: str, ex: int = 300) -> bool:
        """
        設定快取值。
        Args:
            key (str): 快取鍵。
            value (str): 快取值。
            ex (int): 過期秒數。
        Returns:
            bool: 設定成功則 True。
        """
        try:
            if key in self._cache:
                del self._cache[key]
            if len(self._cache) >= self._max_size:
                removed_key, _ = self._cache.popitem(last=False)
                logger.info("[MemoryCache] LRU evict: %s", removed_key)
            now = time.time()
            self._cache[key] = {
                'value': value,
                'expires': now + ex,
                'created': now
            }
            logger.debug("[MemoryCache] Set key: %s", key)
            return True
        except Exception:
            logger.exception("[MemoryCache] Set error for key '%s'", key)
            return False

    def delete(self, key: str) -> bool:
        """
        刪除快取值。
        Args:
            key (str): 快取鍵。
        Returns:
            bool: 刪除成功則 True。
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug("[MemoryCache] Deleted key: %s", key)
            return True
        logger.debug("[MemoryCache] Delete miss for key: %s", key)
        return False


# 全局記憶體快取實例，供裝飾器使用
# 注意：這是一個進程內部的快取，在多進程/多 worker 環境下，每個進程會有自己的獨立快取。
# 若需跨進程共享，應考慮使用 Redis 等外部快取服務。
_global_memory_cache = MemoryCache()


def cache_response(timeout: int = 300) -> Callable:
    """
    回應快取裝飾器。
    用於快取函式（通常是 API 端點）的回應。
    Args:
        timeout (int): 快取失效時間 (秒)。
    Returns:
        Callable: 裝飾器。
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                cache_key_parts = (
                    func.__name__, args, tuple(
                        sorted(
                            kwargs.items())))
                cache_key = f"response_cache:{hash(json.dumps(cache_key_parts, sort_keys=True, default=str))}"
            except TypeError:
                logger.warning(
                    "[cache_response] Args for '%s' not JSON serializable. "
                    "Fallback to string hash.",
                    func.__name__)
                cache_key = (f"response_cache:{func.__name__}:"
                             f"{hash(str(args) + str(kwargs))}")
            except Exception:
                logger.exception(
                    "[cache_response] Error generating cache key for '%s'",
                    func.__name__)
                cache_key = (f"response_cache:{func.__name__}:"
                             f"{hash(str(args) + str(kwargs))}")

            cached_data = _global_memory_cache.get(cache_key)
            if cached_data:
                logger.debug("[cache_response] Hit for key: %s", cache_key)
                try:
                    return json.loads(cached_data)
                except json.JSONDecodeError:
                    logger.error(
                        "[cache_response] Corrupted cache for key: %s. "
                        "Deleting.",
                        cache_key)
                    _global_memory_cache.delete(cache_key)
            else:
                logger.debug("[cache_response] Miss for key: %s", cache_key)

            result = func(*args, **kwargs)
            try:
                _global_memory_cache.set(
                    cache_key, json.dumps(
                        result, default=str), ex=timeout)
                logger.debug("[cache_response] Set for key: %s", cache_key)
            except TypeError:
                logger.error(
                    "[cache_response] Result for '%s' not JSON serializable. "
                    "Not cached.",
                    func.__name__)
            except Exception:
                logger.exception(
                    "[cache_response] Error setting cache for key: %s",
                    cache_key)
            return result
        return wrapper
    return decorator
