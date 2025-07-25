"""
儲存服務模組
負責與 Redis 和 Cloudinary 互動，處理資料的儲存與檢索。
"""
import json
import redis
import cloudinary
import cloudinary.uploader
from config.settings import AppConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class StorageService:
    """
    儲存服務，封裝與 Redis 和 Cloudinary 的互動。
    """

    def __init__(self, config: AppConfig):
        self.config = config
        try:
            if config.redis_url:
                self.redis_client = redis.from_url(
                    config.redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                self.redis_client.ping()
                logger.info("Redis client connected successfully")
            else:
                logger.warning("Redis URL not configured, storage service will be limited")
                self.redis_client = None
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self.redis_client = None

        try:
            cloudinary.config(
                cloud_name=config.cloudinary_cloud_name,
                api_key=config.cloudinary_api_key,
                api_secret=config.cloudinary_api_secret
            )
            logger.info("Cloudinary configured successfully")
        except Exception as e:
            logger.error(f"Cloudinary configuration failed: {e}")

    def _get_redis_key(self, user_id: str, key_type: str) -> str:
        """生成標準化的 Redis key。"""
        return f"linebot:{user_id}:{key_type}"

    def save_chat_history(self, user_id: str, history: list):
        """儲存對話歷史到 Redis。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "chat_history")
        self.redis_client.set(key, json.dumps(history), ex=self.config.chat_history_ttl)

    def get_chat_history(self, user_id: str) -> list:
        """從 Redis 檢索對話歷史。"""
        if not self.redis_client: return []
        key = self._get_redis_key(user_id, "chat_history")
        history_json = self.redis_client.get(key)
        return json.loads(history_json) if history_json else []

    def clear_chat_history(self, user_id: str):
        """清除使用者的對話歷史。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "chat_history")
        self.redis_client.delete(key)

    def save_user_last_image_bytes(self, user_id: str, image_bytes: bytes):
        """儲存使用者最後傳送的圖片二進位內容。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "last_image_bytes")
        self.redis_client.set(key, image_bytes, ex=3600) # 存活一小時

    def get_user_last_image_bytes(self, user_id: str) -> bytes | None:
        """檢索使用者最後傳送的圖片二進位內容。"""
        if not self.redis_client: return None
        key = self._get_redis_key(user_id, "last_image_bytes")
        return self.redis_client.get(key)

    def cache_image_analysis(self, image_hash: str, analysis_result: str, ttl: int = 86400):
        """快取圖片分析結果 (24小時)"""
        if not self.redis_client: return
        key = f"linebot:image_analysis:{image_hash}"
        self.redis_client.set(key, analysis_result, ex=ttl)

    def get_cached_image_analysis(self, image_hash: str) -> str | None:
        """取得快取的圖片分析結果"""
        if not self.redis_client: return None
        key = f"linebot:image_analysis:{image_hash}"
        result = self.redis_client.get(key)
        return result.decode('utf-8') if result else None

    def cache_generated_image(self, prompt_hash: str, image_url: str, ttl: int = 604800):
        """快取生成的圖片 URL (7天)"""
        if not self.redis_client: return
        key = f"linebot:generated_image:{prompt_hash}"
        self.redis_client.set(key, image_url, ex=ttl)

    def get_cached_generated_image(self, prompt_hash: str) -> str | None:
        """取得快取的生成圖片 URL"""
        if not self.redis_client: return None
        key = f"linebot:generated_image:{prompt_hash}"
        result = self.redis_client.get(key)
        return result.decode('utf-8') if result else None

    def set_user_last_location(self, user_id: str, latitude: float, longitude: float):
        """儲存使用者最後分享的位置。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "last_location")
        location_data = json.dumps({"latitude": latitude, "longitude": longitude})
        self.redis_client.set(key, location_data, ex=3600) # 存活一小時

    def get_user_last_location(self, user_id: str) -> dict | None:
        """檢索使用者最後分享的位置。"""
        if not self.redis_client: return None
        key = self._get_redis_key(user_id, "last_location")
        location_json = self.redis_client.get(key)
        return json.loads(location_json) if location_json else None

    def set_user_state(self, user_id: str, state: str, ttl: int = 300):
        """設定使用者的當前狀態。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "state")
        self.redis_client.set(key, state, ex=ttl)

    def get_user_state(self, user_id: str) -> str | None:
        """檢索使用者的當前狀態。"""
        if not self.redis_client: return None
        key = self._get_redis_key(user_id, "state")
        return self.redis_client.get(key)

    def set_nearby_query(self, user_id: str, query: str):
        """暫存使用者的附近地點查詢。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "nearby_query")
        self.redis_client.set(key, query, ex=self.config.nearby_query_ttl)

    def get_nearby_query(self, user_id: str) -> str | None:
        """檢索使用者暫存的附近地點查詢。"""
        if not self.redis_client: return None
        key = self._get_redis_key(user_id, "nearby_query")
        return self.redis_client.get(key)

    def delete_nearby_query(self, user_id: str):
        """刪除使用者暫存的附近地點查詢。"""
        if not self.redis_client: return
        key = self._get_redis_key(user_id, "nearby_query")
        self.redis_client.delete(key)

    def upload_image(self, image_bytes: bytes) -> tuple[str | None, str | None]:
        """上傳圖片到 Cloudinary 並回傳 URL。"""
        try:
            upload_result = cloudinary.uploader.upload(image_bytes)
            return upload_result.get('url'), None
        except Exception as e:
            logger.error(f"Cloudinary upload failed: {e}")
            return None, str(e)
